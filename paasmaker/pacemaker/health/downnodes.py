
import uuid
import datetime

import paasmaker
from paasmaker.common.core import constants

from base import BaseHealthCheck, BaseHealthCheckTest

import colander

class DownNodesHealthCheckParametersSchema(colander.MappingSchema):
	node_timeout = colander.SchemaNode(colander.Integer(),
		title="Node timeout",
		description="The number of seconds since the last response from the node, to consider it down.",
		default=90,
		missing=90)

class DownNodesHealthCheck(BaseHealthCheck):
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: DownNodesHealthCheckParametersSchema(),
	}

	def check(self, parent_job_id, callback, error_callback):
		timeout = self.parameters['node_timeout']
		session = self.configuration.get_database_session()

		my_node = session.query(
			paasmaker.model.Node
		).filter(
			paasmaker.model.Node.uuid == self.configuration.get_node_uuid()
		).first()

		if not my_node:
			error_message = "I'm having an identity crisis. I can't find my own node record."
			self.logger.error(error_message)
			error_callback(error_message)
			return

		# If our uptime is less than the timeout, don't perform the check,
		# because nodes might not have had time to report in to us yet.
		if my_node.uptime() < timeout:
			self.logger.info("Our node has been up for %d seconds.", my_node.uptime())
			self.logger.info("This isn't enough time for other nodes to have reported in within the %d second threshold.", timeout)
			self.logger.info("Therefore, no action is to be taken at this time.")
			callback({}, "Waiting for more uptime.")
			return

		self.logger.info("Looking for nodes that haven't reported in for %d seconds...", timeout)

		# Now find any nodes that haven't reported in for a while.
		before_time = datetime.datetime.utcnow() - datetime.timedelta(0, timeout)
		bad_nodes = session.query(
			paasmaker.model.Node.id
		).filter(
			paasmaker.model.Node.last_heard < before_time,
			paasmaker.model.Node.state == constants.NODE.ACTIVE
		)
		bad_nodes_count = bad_nodes.count()

		self.logger.info("Found %d down nodes.", bad_nodes_count)

		if bad_nodes_count > 0:
			full_node_list = session.query(
				paasmaker.model.Node
			).filter(
				paasmaker.model.Node.id.in_(bad_nodes)
			)

			self.logger.info("Failed nodes:")
			for node in full_node_list:
				self.logger.info("- %s (%s:%d, %s)", node.name, node.route, node.apiport, node.uuid[0:8])

		# Find any can-run instances on that node.
		down_instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.node_id.in_(bad_nodes),
			paasmaker.model.ApplicationInstance.state.in_(constants.INSTANCE_ALLOCATED_STATES)
		)

		altered_instance_count = down_instances.count()

		# Mark instances as down first. If we did nodes first, then this doesn't work
		# as the matched set of bad nodes then changes.
		if altered_instance_count > 0:
			# Force it to generate a list now.
			fix_down_instances = down_instances.all()

			# Then update the instances.
			self.logger.critical("Marked %d instances as DOWN.", altered_instance_count)
			down_instances.update(
				{
					'state': constants.INSTANCE.DOWN
				},
				synchronize_session=False
			)

		# Then nodes.
		if bad_nodes_count > 0:
			self.logger.critical("Updating %d nodes to DOWN.", bad_nodes_count)
			bad_nodes.update({'state': constants.NODE.DOWN})

		# If we have changes to commit, do that.
		if bad_nodes_count > 0 or altered_instance_count > 0:
			session.commit()

		self.return_context = {
			'bad_nodes': bad_nodes_count,
			'down_instances': altered_instance_count
		}
		self.return_message = "Completed down nodes check. Found %d down nodes, and marked %d instances as down." % (bad_nodes_count, altered_instance_count)
		self.callback = callback

		if altered_instance_count > 0:
			# Queue up jobs to remove those instances from the routing table.
			def add_fix_instance(job_id=None):
				if job_id:
					self.logger.info("Added job %s to fix routing for an instance.", job_id)
				try:
					instance = fix_down_instances.pop()

					paasmaker.common.job.routing.routing.RoutingUpdateJob.setup_for_instance(
						self.configuration,
						session,
						instance,
						False,
						add_fix_instance
					)
				except IndexError, ex:
					# No more to process.
					self._finish_check()

				# end of add_fix_instance()

			add_fix_instance()
		else:
			# No jobs to queue. We're done.
			self._finish_check()

	def _finish_check(self):
		self.callback(
			self.return_context,
			self.return_message
		)

class DownNodesHealthCheckTest(BaseHealthCheckTest):

	def setUp(self):
		super(DownNodesHealthCheckTest, self).setUp()

		self.registry.register(
			'paasmaker.health.downnodes',
			'paasmaker.pacemaker.health.downnodes.DownNodesHealthCheck',
			{},
			'Down Nodes health check'
		)

	def test_identity_crisis(self):
		# The check will attempt to look for it's own node.
		# If it can't, it will fail.
		health = self.registry.instantiate(
			'paasmaker.health.downnodes',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{}
		)

		health.check(
			None,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertFalse(self.success, "Should have failed.")
		self.assertIn("identity", self.message, "Should have had an identity crisis.")

	def test_standard(self):
		health = self.registry.instantiate(
			'paasmaker.health.downnodes',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{}
		)

		# Create our node record.
		our_uuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(our_uuid)

		session = self.configuration.get_database_session()
		node = paasmaker.model.Node('test', 'localhost', 12345, our_uuid, constants.NODE.ACTIVE)
		session.add(node)
		session.commit()

		# Now create a node that should remain up.
		up_uuid = str(uuid.uuid4())
		up_node = paasmaker.model.Node('test_up', 'localhost', 12346, up_uuid, constants.NODE.ACTIVE)
		session.add(up_node)

		# Create a node that should be down - as in, it last reported in more than 90 seconds ago.
		down_uuid = str(uuid.uuid4())
		down_node = paasmaker.model.Node('test_down', 'localhost', 12347, down_uuid, constants.NODE.ACTIVE)
		down_node.last_heard = datetime.datetime.utcnow() - datetime.timedelta(0, 120)
		session.add(down_node)

		session.commit()

		# Now run the check, and see what happened.
		health.check(
			None,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It should be waiting for more uptime before doing any checks.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(len(self.context), 0, "Should not have emitted context.")
		self.assertIn("uptime", self.message, "Message should have mentioned uptime.")

		# Now, reset our node so it's had enough uptime itself to start checking.
		session.refresh(node)
		node.start_time = node.start_time - datetime.timedelta(0, 300)
		session.add(node)
		session.commit()

		# Now run the check, and see what happened.
		health.check(
			None,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It should have reported success - but marked one node as down.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertTrue(self.context.has_key('bad_nodes'), "Missing output context.")
		self.assertTrue(self.context.has_key('down_instances'), "Missing output context.")
		self.assertEquals(self.context['bad_nodes'], 1, "Wrong number of bad nodes.")
		self.assertEquals(self.context['down_instances'], 0, "Detected down instances?")

		session.refresh(up_node)
		session.refresh(down_node)

		self.assertEquals(up_node.state, constants.NODE.ACTIVE, "Up node was altered.")
		self.assertEquals(down_node.state, constants.NODE.DOWN, "Down node was not altered.")

		# Change the down node back.
		down_node.state = constants.NODE.ACTIVE
		session.add(down_node)
		session.commit()

		# Create a sample application with a few instances.
		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			{},
			'1',
			'tornado-simple'
		)

		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(instance_type.id)

		# The instance on the up node first.
		instance_up = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			up_node
		)

		instance_up.state = constants.INSTANCE.RUNNING
		session.add(instance_up)

		# Then an instance on the down node.
		instance_down = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			down_node
		)

		instance_down.state = constants.INSTANCE.RUNNING
		session.add(instance_down)

		session.commit()

		# Now health check again.
		health.check(
			None,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It should have reported success - but marked one node as down.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['down_instances'], 1, "Wrong number of down instances.")

		# Refresh the two instances.
		session.refresh(instance_up)
		session.refresh(instance_down)

		self.assertEquals(instance_up.state, constants.INSTANCE.RUNNING, "Incorrectly failed an instance.")
		self.assertEquals(instance_down.state, constants.INSTANCE.DOWN, "Didn't mark an instance as down.")


import uuid
import datetime

import paasmaker
from paasmaker.common.core import constants

from base import BaseHealthCheck, BaseHealthCheckTest

from pubsub import pub
import colander

class RouterDownInstancesHealthCheckParametersSchema(colander.MappingSchema):
	state_change_wait = colander.SchemaNode(colander.Integer(),
		title="State Change Wait",
		description="The number of seconds after the last update to work on. See the documentation for a full description.",
		default=60,
		missing=60)

class RouterDownInstancesHealthCheck(BaseHealthCheck):
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: RouterDownInstancesHealthCheckParametersSchema(),
	}
	API_VERSION = "0.9.0"

	def check(self, parent_job_id, callback, error_callback):
		# TODO: Refactor this so it's not quite so deeply nested.
		self.checked_instances = 0
		self.removed_instances = 0

		def on_dump_complete(table, serial, session):
			if len(table) == 0:
				# No routing table just yet.
				session.close()

				callback(
					{
						'router_table_checked_instances': self.checked_instances,
						'router_table_removed_instances': self.removed_instances
					},
					"Router table does not have any entries."
				)
				return

			self.logger.info("Checking router table serial %s." % serial)
			self.logger.info("Checking %d entries in the routing table.", len(table))

			# Now that we have the table, go over it.
			# If we find any instances that are not in the RUNNING state
			# (and the time has expired), remove them from the routing table.
			def process_entry():
				try:
					entry = table.pop()

					self.logger.debug("Entry %s has %d instances.", entry['hostname'], len(entry['instances']))

					def process_instance(job_id=None):
						try:
							instance = entry['instances'].pop()
							self.checked_instances += 1

							if instance.updated_age() > self.parameters['state_change_wait'] and instance.state != constants.INSTANCE.RUNNING:
								# Not running? Should not be in routing table.
								self.logger.error("Instance %s is in state %s and is in the routing table.", instance.instance_id, instance.state)
								self.removed_instances += 1
								paasmaker.common.job.routing.RoutingUpdateJob.setup_for_instance(
									self.configuration,
									session,
									instance,
									False,
									process_instance,
									parent=parent_job_id
								)
							else:
								# It's fine.
								process_instance()

						except IndexError, ex:
							# No more instances.
							# Move onto next entry.
							process_entry()

						# end of process_instance()

					# Kick off the instance processing.
					process_instance()

				except IndexError, ex:
					def done_executable():
						callback(
							{
								'router_table_checked_instances': self.checked_instances,
								'router_table_removed_instances': self.removed_instances
							},
							"Checked %d instances in the router table, removed %d." % (self.checked_instances, self.removed_instances)
						)

					# No more entries.
					session.close()
					# Finish up.
					self.configuration.job_manager.allow_execution(parent_job_id, done_executable)

				# end of process_entry()

			# Kick off the process.
			process_entry()

		# Dump the routing table.
		dumper = paasmaker.router.tabledump.RouterTableDump(self.configuration, on_dump_complete, error_callback)
		dumper.dump()

class RouterDownInstancesHealthCheckTest(BaseHealthCheckTest):

	def setUp(self):
		super(RouterDownInstancesHealthCheckTest, self).setUp()

		self.registry.register(
			'paasmaker.health.routerdowninstances',
			'paasmaker.pacemaker.health.routerdowninstances.RouterDownInstancesHealthCheck',
			{},
			'Router Down Instances health check'
		)

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_standard(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		health = self.registry.instantiate(
			'paasmaker.health.routerdowninstances',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{}
		)

		# Now create a node that should remain up.
		up_uuid = str(uuid.uuid4())
		up_node = paasmaker.model.Node('test_up', 'localhost', 12346, up_uuid, constants.NODE.ACTIVE)
		session.add(up_node)
		session.commit()

		# Create a container job.
		self.configuration.job_manager.add_job('paasmaker.job.container', {}, "Example job.", self.stop)
		job_id = self.wait()

		# Now run the check, and see what happened.
		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It shouldn't have done anything, but should have succeeded at doing nothing.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.message, "Router table does not have any entries.")
		self.assertEquals(self.context['router_table_checked_instances'], 0, "Should not have checked any instances.")

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

		instance_running = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			up_node
		)

		instance_running.state = constants.INSTANCE.RUNNING
		instance_running.port = 12345
		session.add(instance_running)
		session.commit()

		version = session.query(
			paasmaker.model.ApplicationVersion
		).get(instance_type.application_version_id)

		version.state = constants.VERSION.RUNNING
		session.add(version)
		session.commit()

		# Add it to the routing table.
		paasmaker.common.job.routing.RoutingUpdateJob.setup_for_instance(
			self.configuration,
			session,
			instance_running,
			True,
			self.stop
		)

		# Now make that job executable.
		routing_job_id = self.wait()
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(routing_job_id))
		self.configuration.job_manager.allow_execution(routing_job_id, self.stop)
		self.wait()

		# Wait for that job to finish.
		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS)

		# Recreate the plugin, and make it look into the future.
		health = self.registry.instantiate(
			'paasmaker.health.routerdowninstances',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{'state_change_wait': 0}
		)

		# Run the health check. It should not detect any errors.
		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It shouldn't have done anything, but should have succeeded at doing nothing.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['router_table_checked_instances'], 1, "Didn't check any instances.")
		self.assertEquals(self.context['router_table_removed_instances'], 0, "Performed stop actions.")

		# Stop that instance, and run again.
		instance_running.state = constants.INSTANCE.STOPPED
		session.add(instance_running)
		session.commit()

		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['router_table_checked_instances'], 1, "Didn't check any instances.")
		self.assertEquals(self.context['router_table_removed_instances'], 1, "Didn't remove any entries.")

		# Wait for the root job to finish.
		# TODO: The timings mean this doesn't work properly, as it subscribes too
		# late and misses the relevant update, but if we subscribe earlier it interferes
		# with the unit test waiting for the health check to succeed.
		# I have confirmed that this works though, and the next part of the unit test
		# confirms this too.

		# pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))
		# result = self.wait()
		# while result is None or result.state != constants.JOB.SUCCESS:
		# 	result = self.wait()

		# self.assertEquals(result.state, constants.JOB.SUCCESS, "Routing update did not succeed.")

		self.short_wait_hack(length=0.3)

		# Run the check again. There should be no instances in the table now,
		# so it should succeed.
		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['router_table_checked_instances'], 0, "Checked some instances.")
		self.assertEquals(self.context['router_table_removed_instances'], 0, "Did remove some entries.")
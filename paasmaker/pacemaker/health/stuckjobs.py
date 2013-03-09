
import uuid
import datetime

import paasmaker
from paasmaker.common.core import constants

from base import BaseHealthCheck, BaseHealthCheckTest

import colander

class StuckJobsHealthCheckParametersSchema(colander.MappingSchema):
	pass

class StuckJobsHealthCheck(BaseHealthCheck):
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: StuckJobsHealthCheckParametersSchema(),
	}
	API_VERSION = "0.9.0"

	def check(self, parent_job_id, callback, error_callback):
		# Find jobs that are on nodes that are down.
		# Abort the trees to allow other jobs or systems to kick in.
		self.session = self.configuration.get_database_session()
		self.down_nodes = self.session.query(
			paasmaker.model.Node
		).filter(
			paasmaker.model.Node.state == constants.NODE.DOWN
		).all()

		self.callback = callback
		self.error_callback = error_callback

		self.down_nodes_count = len(self.down_nodes)
		self.cancelled_jobs = 0

		self.logger.info("Checking %d down nodes.", self.down_nodes_count)

		self.configuration.io_loop.add_callback(self._fetch_down_node)

	def _fetch_down_node(self):
		try:
			node = self.down_nodes.pop()

			self._process_down_node(node)

		except IndexError, ex:
			# No more to work on.
			self.session.close()
			self.callback(
				{
					'cancelled_jobs': self.cancelled_jobs
				},
				"Checked %d down nodes, cancelled %d jobs." % (self.down_nodes_count, self.cancelled_jobs)
			)

	def _process_down_node(self, node):
		# Find those stuck jobs.
		def got_stuck_jobs(jobs):
			if len(jobs) > 0:
				self.logger.warning("Found %d stuck jobs on node %s. Aborting those jobs.", len(jobs), node.name)

				def fetch_job():
					try:
						def force_abort_complete(result):
							# Next job.
							self.configuration.io_loop.add_callback(fetch_job)
							# end of force_abort_complete()

						job = jobs.pop()

						self.cancelled_jobs += 1

						self.configuration.job_manager.force_abort(job, node.uuid, force_abort_complete)

					except KeyError, ex:
						# No more jobs.
						self.configuration.io_loop.add_callback(self._fetch_down_node)

					# end of fetch_job()

				fetch_job()
			else:
				# No stuck jobs. Excellent!
				self.configuration.io_loop.add_callback(self._fetch_down_node)

			# end of got_stuck_jobs()

		self.configuration.job_manager.get_node_jobs(
			node.uuid,
			got_stuck_jobs,
			state=[constants.JOB.WAITING, constants.JOB.RUNNING]
		)

class StuckJobsHealthCheckTest(BaseHealthCheckTest):

	def setUp(self):
		super(StuckJobsHealthCheckTest, self).setUp()

		self.registry.register(
			'paasmaker.health.stuckjobs',
			'paasmaker.pacemaker.health.stuckjobs.StuckJobsHealthCheck',
			{},
			'Stuck Jobs health check'
		)

	def test_standard(self):
		health = self.registry.instantiate(
			'paasmaker.health.stuckjobs',
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
		down_node = paasmaker.model.Node('test_down', 'localhost', 12347, down_uuid, constants.NODE.DOWN)
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

		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(len(self.context), 1, "Should not have emitted context.")
		self.assertIn(" 1 down", self.message, "Message should have mentioned nodes.")
		self.assertEquals(self.context['cancelled_jobs'], 0, "Should not have cancelled any jobs.")

		# Submit a job on the down node.
		self.configuration.job_manager.add_job(
			'paasmaker.job.container',
			{},
			"Example job.",
			self.stop,
			node=down_node.uuid
		)
		job_id = self.wait()
		self.configuration.job_manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		# Call the check again.
		health.check(
			None,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It should have reported success and cancelled one job.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertIn(" 1 down", self.message, "Message should have mentioned nodes.")
		self.assertEquals(self.context['cancelled_jobs'], 1, "Should have cancelled one job.")

		# Wait for a bit.
		self.short_wait_hack()

		# Make sure the job is aborted.
		self.configuration.job_manager.get_job_state(job_id, self.stop)
		state = self.wait()

		self.assertEquals(state, constants.JOB.ABORTED, "State was not aborted.")

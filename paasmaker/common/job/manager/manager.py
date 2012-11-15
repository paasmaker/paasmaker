
import logging
import uuid

import paasmaker
from paasmaker.common.core import constants
from base import BaseJob
from backendredis import RedisJobBackend
from ...testhelpers import TestHelpers

import tornado
from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobManager(object):
	def __init__(self, configuration):
		logger.debug("Initialising JobManager.")
		self.configuration = configuration
		self.backend = RedisJobBackend(configuration)
		self.runners = {}

		logger.debug("Subscribing to job status updates.")
		pub.subscribe(self.job_status, 'job.status')

	def prepare(self, callback, error_callback):
		"""
		Prepare the job manager, setting up the appropriate backend.
		Calls the supplied callbacks when ready.
		"""
		self.backend.setup(callback, error_callback)

	def add_job(self, plugin, parameters, title, callback, parent=None, node=None):
		"""
		Add the given job to the system, calling the callback with the
		assigned job ID when it's inserted into the system. New jobs
		are inserted with the state NEW, which means they won't be executed
		until that tree is moved into the WAITING state.
		"""
		# Sanity check: make sure the given plugin exists
		# and can be called as a job.
		if not self.configuration.plugins.exists(plugin, paasmaker.util.plugin.MODE.JOB):
			raise ValueError("Plugin %s doesn't exist in the JOB mode." % plugin)

		# Generate a job_id.
		job_id = str(uuid.uuid4())
		logger.info("Adding job '%s'", title)
		logger.debug("Allocated job ID %s", job_id)

		# Figure out what node it belongs to. If supplied, use that one.
		# Otherwise it's considered a local job.
		if node:
			resolved_node = node
		else:
			resolved_node = self.configuration.get_node_uuid()

		def on_job_added():
			# Send the NEW status around the cluster. In case something wants it.
			self.configuration.send_job_status(job_id, constants.JOB.NEW)
			# Ok, we added the job. Call the callback with the new job_id.
			logger.debug("Completed adding new job %s.", job_id)
			callback(job_id)

		# Ask the backend to add the job.
		self.backend.add_job(
			resolved_node,
			job_id,
			parent,
			on_job_added,
			state=constants.JOB.NEW,
			plugin=plugin,
			parameters=parameters,
			title=title
		)

	def allow_execution(self, job_id, callback=None):
		"""
		Allow the entire job tree given by job_id (which can be anywhere on the tree)
		to commence execution. Optionally call the callback when done. This does not
		start evaluating jobs, but you can easily have it do that by setting
		the callback to the job managers evaluate function.
		"""
		# TODO: Optionally broadcast a WAITING status to convince other nodes that
		# they should look at their jobs. But make it optional.
		def on_tree_updated(result):
			if callback:
				callback()
		self.backend.set_state_tree(job_id, constants.JOB.NEW, constants.JOB.WAITING, on_tree_updated)

	def _start_job(self, job_id):
		def on_context(context):
			def on_running(result):
				# Finally kick it off...
				logger.debug("Finally kicking off job %s", job_id)
				self.runners[job_id].start_job(context)

			# Now that we have the context, we can start the job off.
			# Mark it as running and then get started.
			# TODO: There might be race conditions here...
			logger.debug("Got context for job %s", job_id)
			logger.debug("Context for job %s: %s", job_id, str(context))
			self.backend.set_attrs(job_id, {'state': constants.JOB.RUNNING}, on_running)

		def on_job_metadata(job):
			# Now that we have the job metadata, we can try to instantiate the plugin.
			logger.debug("Got metadata for job %s", job_id)
			job_logger = self.configuration.get_job_logger(job_id)
			plugin = self.configuration.plugins.instantiate(
				job['plugin'],
				paasmaker.util.plugin.MODE.JOB,
				job['parameters'],
				job_logger
			)
			plugin.configure(self, job_id)

			self.runners[job_id] = plugin

			# Now we need to fetch the context to start the job off.
			self.backend.get_context(job_id, on_context)

		# Kick off the request to get the job data.
		logger.debug("Fetching job data for %s to start it.", job_id)
		self.backend.get_job(job_id, on_job_metadata)

	def evaluate(self):
		"""
		Evaluate our nodes jobs, and start the ones that are ready to execute.
		"""
		def on_ready_list(jobs):
			logger.debug("Found %d jobs ready to run.", len(jobs))
			for job in jobs:
				logger.debug("Launching %s...", job)
				self._start_job(job)

		logger.debug("Fetching list of ready to run jobs.")
		self.backend.get_ready_to_run(
			self.configuration.get_node_uuid(),
			constants.JOB.WAITING, # The state of jobs that can be started.
			constants.JOB.SUCCESS, # The state that all child jobs have to be in to trigger starting.
			on_ready_list
		)

	def completed(self, job_id, state, context, summary):
		# Apparently this job has finished in some state.
		def on_state_updated(job):
			# Remove the runner instance.
			if self.runners.has_key(job_id):
				del self.runners[job_id]
			# Now publish the fact that the job has reached the given state.
			self.configuration.send_job_status(job_id, state)

		def on_context_updated():
			# Update the job state first.
			self.backend.set_attrs(
				job_id,
				{
					'state': state,
					'summary': summary
				},
				on_state_updated
			)

		logger.debug("Job %s reports state %s.", job_id, state)
		# Update the job context first. In case something
		# swoops in and starts executing other jobs.
		if context:
			self.backend.store_context(job_id, context, on_context_updated)
		else:
			# Skip directly to the context updated callback,
			# which changes the job state.
			on_context_updated()

	def handle_failure(self, message):
		# Ok, so a job has failed. In the tree centered around the
		# supplied job ID, locate and fail the rest of the jobs on our node.
		# Stop all the WAITING ones first.
		def on_waiting_altered(jobs):
			logger.debug("Completed altering jobs.")

		def on_running(jobs):
			logger.info("Found %d running jobs on our node that need to be aborted.", len(jobs))
			# If we have matching runner instances, abort them.
			for job in jobs:
				if self.runners.has_key(job):
					logger.debug("Aborting job %s.", job)
					runner = self.runners[job]
					# Queue it up - we don't want to do it right now.
					# The abort_job() will call us back later when it's finished.
					# At that stage we change state from RUNNING to ABORTED.
					self.configuration.io_loop.add_callback(runner.abort_job)
				else:
					logger.warn("Unable to find job %s that's supposed to be running. Ignoring.", job)

		logger.debug("Searching for WAITING jobs, and adjusting to aborted for tree %s.", message.job_id)
		self.backend.set_state_tree(
			message.job_id,
			constants.JOB.WAITING,
			constants.JOB.ABORTED,
			on_waiting_altered,
			node=self.configuration.get_node_uuid()
		)

		# Whilst that's going on, find the running jobs and sort them out.
		logger.debug("Searching for RUNNING jobs and cancelling for tree %s.", message.job_id)
		self.backend.get_tree(
			message.job_id,
			on_running,
			state=constants.JOB.RUNNING,
			node=self.configuration.get_node_uuid()
		)

	def job_status(self, message):
		# No need to do anything if we're not in an interesting state.
		if message.state in constants.JOB_SUCCESS_STATES:
			# Something succeeded. Let's evaluate our jobs again.
			self.configuration.io_loop.add_callback(self.evaluate)

		if message.state in constants.JOB_ERROR_STATES:
			# Something failed or was aborted.
			def failed():
				self.handle_failure(message)
			self.configuration.io_loop.add_callback(failed)

		# And for everything else... we do nothing.

	def get_job_state(self, job_id, callback):
		def on_attr(value):
			callback(value)
		self.backend.get_attr(job_id, 'state', on_attr)

	def abort(self, job_id):
		# Broadcast the abort request. Everything else will then
		# sort itself out.
		self.configuration.send_job_status(job_id, constants.JOB.ABORTED)

class TestSuccessJobRunner(BaseJob):
	def start_job(self, context):
		self.success({}, "Completed successfully.")

	def abort_job(self):
		self.aborted("Aborted.")

class TestFailJobRunner(BaseJob):
	def start_job(self, context):
		self.failed("Failed to run.")

	def abort_job(self):
		self.aborted("Aborted.")

class TestAbortJobRunner(BaseJob):
	def start_job(self, context):
		# Do nothing - we're running now.
		pass

	def abort_job(self):
		self.aborted("Aborted.")

class JobManagerTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(JobManagerTest, self).setUp()
		pub.subscribe(self.on_job_status, 'job.status')
		self.statuses = {}
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid('test')

		self.configuration.plugins.register(
			'paasmaker.job.success',
			'paasmaker.common.job.manager.manager.TestSuccessJobRunner',
			{}
		)
		self.configuration.plugins.register(
			'paasmaker.job.failure',
			'paasmaker.common.job.manager.manager.TestFailJobRunner',
			{}
		)
		self.configuration.plugins.register(
			'paasmaker.job.aborted',
			'paasmaker.common.job.manager.manager.TestAbortJobRunner',
			{}
		)

		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(JobManagerTest, self).tearDown()

	def on_job_status(self, message):
		self.statuses[message.job_id] = message

	def get_state(self, job_id):
		self.manager.get_job_state(job_id, self.stop)
		return self.wait()

	def test_manager_success_simple(self):
		# Set up a simple successful job.
		self.manager.add_job('paasmaker.job.success', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, self.stop)
		self.wait()
		self.manager.evaluate()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.SUCCESS, 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		self.manager.add_job('paasmaker.job.failure', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, self.stop)
		self.wait()
		self.manager.evaluate()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job was not a failure.')

	def test_manager_success_tree(self):
		# Test that a subtree processes correctly.
		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id)
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, self.stop)
		self.wait()

		#self.dump_job_tree(root_id, self.manager.backend)
		#self.wait()

		self.manager.evaluate()

		self.short_wait_hack(length=0.2)

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.SUCCESS, "Sub 2 should have succeeded.")
		self.assertEquals(root_status, constants.JOB.SUCCESS, "Root should have succeeded.")

	def test_manager_failed_subtree(self):
		# Test that a subtree fails correctly.
		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id)
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.failure', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, self.stop)
		self.wait()

		#self.dump_job_tree(root_id, self.manager.backend)
		#self.wait()

		self.manager.evaluate()

		self.short_wait_hack(length=0.2)

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.FAILED, "Sub 2 should have failed.")
		self.assertEquals(root_status, constants.JOB.ABORTED, "Root should have been aborted.")

	def test_manager_abort_tree(self):
		# Test that a subtree fails correctly.
		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id)
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.aborted', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, self.stop)
		self.wait()

		#self.dump_job_tree(root_id, self.manager.backend)
		#self.wait()

		self.manager.evaluate()

		self.short_wait_hack(length=0.2)
		self.manager.abort(sub2_id)
		self.short_wait_hack(length=0.2)

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.ABORTED, "Sub 2 should have failed.")
		self.assertEquals(root_status, constants.JOB.ABORTED, "Root should have been aborted.")
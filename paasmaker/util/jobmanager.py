
import uuid
import time
import paasmaker
from pubsub import pub
import tornado
import tornado.testing
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobRunner(object):
	"""
	Mixin for other classes to make them into job runnable objects.
	"""
	def set_job_parameters(self, job_id, manager):
		self.job_manager = manager
		self.job_id = job_id
		self.job_cached_logger = None
		self.job_children = {}
		self.job_running = False
		self.job_aborted = False

	def add_child_job(self, job):
		self.job_children[job.job_id] = job

	def completed_child_job(self, job_id):
		if self.job_children.has_key(job_id):
			del self.job_children[job_id]

	def is_ready(self):
		return not self.job_running and not self.job_aborted and len(self.job_children.keys()) == 0

	def start_job(self):
		raise NotImplementedError("Start is not implemented.")

	def abort_job(self):
		"""
		Override to take action to stop your processes, if you can.
		You do not need to run aborted_job() to report your status,
		because abort_job() is only called for external inputs, not your
		own. If you don't want to implement this (or don't need to) just
		override this function and do nothing in it.
		"""
		raise NotImplementedError("Abort is not implemented.")

	def start_job_helper(self):
		if not self.job_aborted:
			self.job_running = True
			self.job_manager.configuration.send_job_status(self.job_id, state='RUNNING')
			self.start_job()

	def finished_job(self, state, summary):
		self.job_manager.finished(self.job_id, state, summary)

	def aborted_job(self, summary):
		self.job_aborted = True
		self.finished_job('ABORTED', summary)

	def job_logger(self):
		if self.job_cached_logger:
			return self.job_cached_logger

		self.job_cached_logger = self.job_manager.configuration.get_job_logger(self.job_id)

		return self.job_cached_logger

class JobManager(object):
	def __init__(self, configuration, io_loop=None):
		logger.debug("Initialising JobManager.")
		self.configuration = configuration
		# Map job_id => job
		self.jobs = {}
		# Map child_id => parent_id
		self.parents = {}
		if io_loop:
			logger.debug("Using supplied IO loop.")
			self.io_loop = io_loop
		else:
			logger.debug("Using global IO loop.")
			self.io_loop = tornado.ioloop.IOLoop.instance()

		logger.debug("Subscribing to job status updates.")
		pub.subscribe(self.job_status_change, 'job.status')

	def add_job(self, job_id, job):
		logger.debug("Adding job object for %s", job_id)
		if not isinstance(job, JobRunner):
			raise ValueError("job parameter should be instance of JobRunner.")
		job.set_job_parameters(job_id, self)
		self.jobs[job_id] = job
		logger.debug("Job %s is now stored.", job_id)

	def add_child_job(self, parent_id, child_id):
		if not self.jobs.has_key(parent_id):
			raise KeyError("No such parent job %s" % parent_id)
		if not self.jobs.has_key(child_id):
			raise KeyError("No such child job %s" % child_id)
		logger.debug("Parent %s adding child %s", parent_id, child_id)
		parent = self.jobs[parent_id]
		child = self.jobs[child_id]
		parent.add_child_job(child)
		self.parents[child_id] = parent_id
		logger.debug("Completed parent %s adding child %s", parent_id, child_id)

		# Advertise that the job is now waiting, and the parent/child relationship.
		# TODO: Test this. Probably via the audit writer?
		self.configuration.send_job_status(child_id, state='WAITING', parent_id=parent_id)

	def evaluate(self):
		# Evaluate and kick off any jobs that can be started now.
		started_count = 0
		logger.debug("Commencing job evaluation of %d entries", len(self.jobs))
		for job_id, job in self.jobs.iteritems():
			if job.is_ready():
				logger.debug("Job %s is ready, placing on IO loop.", job_id)
				# Do this on the IO loop, so it cooperates with everything else.
				self.io_loop.add_callback(job.start_job_helper)
				started_count += 1

		logger.debug("Started %d (of %d) jobs this evaluation.", started_count, len(self.jobs))
		return started_count

	def finished(self, job_id, state, summary):
		# Pipe off this to any listeners who want to know.
		logger.debug("Signalling finished for job %s with state %s", job_id, state)
		self.configuration.send_job_status(job_id, state=state, summary=summary)

	def abort(self, job_id, reason="Aborted by user or system request."):
		# Just signal that it's done. The callback will clean them all up.
		logger.debug("Signalling abort for job %s.", job_id)
		self.finished(job_id, 'ABORTED', reason)

	def find_entire_subtree(self, parent):
		subtree = {}
		subtree.update(parent.job_children)
		for child_id, child in parent.job_children.iteritems():
			subtree.update(self.find_entire_subtree(child))
		return subtree

	def handle_fail(self, job_id):
		logger.debug("Handling failure for job id %s", job_id)
		# Find the ultimate parent of this job.
		parent_id = job_id
		# TODO: Check if we even have this job.
		parent = self.jobs[job_id]
		while self.parents.has_key(parent_id):
			if self.jobs.has_key(parent_id):
				parent = self.jobs[self.parents[parent_id]]
				parent_id = parent.job_id

		logger.debug("Ultimate parent of %s is %s.", job_id, parent_id)

		# Now find the entire subtree for that job.
		subtree = self.find_entire_subtree(parent)
		subtree[parent.job_id] = parent

		logger.debug("Found %d jobs in subtree for ultimate parent %s (source job %s)", len(subtree), parent_id, job_id)

		# Remove this subtree from the internal database.
		# This stops re-entrant kind of issues when we publish
		# the aborted status.
		for key in subtree:
			if self.jobs.has_key(key):
				del self.jobs[key]
			if self.parents.has_key(key):
				del self.parents[key]

		# Remove this job from the subtree - it's already failed/aborted.
		del subtree[job_id]

		logger.debug("Purged internal tree in handling failure for %s", job_id)

		# Now fail them all.
		for key, job in subtree.iteritems():
			if job.job_running:
				logger.debug("Job %s was running, asking it to abort.", key)
				job.abort_job()
			# Mark it as aborted (in case it's on the IO loop awaiting startup)
			job.job_aborted = True
			# Send the status of aborted.
			self.finished(key, 'ABORTED', 'A related job failed or was aborted, so this job was aborted.')

		logger.debug("Subtree aborted (source job %s)", job_id)

	def job_status_change(self, job_id=None, state=None, source=None):
		# Not in our database? Do nothing.
		if not self.jobs.has_key(job_id):
			logger.debug("Got message for job that's not in our database - job %s", job_id)
			return

		# Handle the incoming states.
		if state in paasmaker.common.core.constants.JOB_ERROR_STATES:
			logger.debug("Job %s in state %s - handling failure.", job_id, state)
			# That job failed, or was aborted. Kill off related jobs.
			self.handle_fail(job_id)

		if state in paasmaker.common.core.constants.JOB_SUCCESS_STATES:
			logger.debug("Job %s in state %s - evaluating new jobs for startup.", job_id, state)
			# Success! Mark it as complete, then evaluate our jobs again.
			# Does this job have a parent? If so, remove this job from
			# the list, so it goes on to process the next one.
			if self.parents.has_key(job_id) and self.jobs[self.parents[job_id]]:
				parent_id = self.parents[job_id]
				parent = self.jobs[parent_id]
				parent.completed_child_job(job_id)
				del self.parents[job_id]
			if self.jobs.has_key(job_id):
				del self.jobs[job_id]

			# Now evaluate jobs and take the appropriate actions.
			# NOTE: We only evaluate jobs on successful states.
			self.evaluate()

class TestSuccessJobRunner(JobRunner):
	def start_job(self):
		self.finished_job('SUCCESS', "Completed successfully.")

	def abort_job(self):
		pass

class TestFailJobRunner(JobRunner):
	def start_job(self):
		self.finished_job('FAILED', "Failed to complete.")

	def abort_job(self):
		pass

class TestAbortJobRunner(JobRunner):
	def start_job(self):
		# Do nothing. In theory, we're now running.
		pass

	def abort_job(self):
		# Do something?
		pass

class JobManagerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(JobManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'])
		self.configuration.set_node_uuid('test')
		self.manager = JobManager(self.configuration, self.io_loop)
		pub.subscribe(self.on_job_status, 'job.status')
		self.statuses = {}

	def tearDown(self):
		pub.unsubscribe(self.on_job_status, 'job.status')
		self.configuration.cleanup()
		super(JobManagerTest, self).tearDown()

	def on_job_status(self, **kwargs):
		#print str(kwargs)
		# TODO: This storage overwrites the previous state. But I guess we're
		# generally waiting for it to end up in a particular end state...
		self.statuses[kwargs['job_id']] = kwargs

	def get_state(self, job_id):
		if self.statuses.has_key(job_id):
			return self.statuses[job_id]
		else:
			return {'state': 'UNKNOWN', 'job_id': job_id}

	def jid(self):
		return str(uuid.uuid4())

	def test_manager_success_simple(self):
		# Set up a simple successful job.
		job_id = self.jid()
		job = TestSuccessJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result['state'], 'SUCCESS', 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		job_id = self.jid()
		job = TestFailJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result['state'], 'FAILED', 'Test job was not a failure.')

	def test_manager_success_tree(self):
		# Test that a subtree processes correctly.
		root = TestSuccessJobRunner()
		sub1 = TestSuccessJobRunner()
		sub2 = TestSuccessJobRunner()
		subsub1 = TestSuccessJobRunner()

		root_id = self.jid()
		sub1_id = self.jid()
		sub2_id = self.jid()
		subsub1_id = self.jid()

		# Add the jobs.
		self.manager.add_job(root_id, root)
		self.manager.add_job(sub1_id, sub1)
		self.manager.add_job(sub2_id, sub2)
		self.manager.add_job(subsub1_id, subsub1)

		# And then their relationships.
		self.manager.add_child_job(root_id, sub1_id)
		self.manager.add_child_job(sub1_id, subsub1_id)
		self.manager.add_child_job(root_id, sub2_id)

		# Start processing them.
		self.manager.evaluate()

		self.short_wait_hack()

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status['state'], 'SUCCESS', "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status['state'], 'SUCCESS', "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status['state'], 'SUCCESS', "Sub 2 should have succeeded.")
		self.assertEquals(root_status['state'], 'SUCCESS', "Root should have succeeded.")

	def test_manager_failed_subtree(self):
		# Test that a subtree fails correctly.
		root = TestSuccessJobRunner()
		sub1 = TestSuccessJobRunner()
		sub2 = TestFailJobRunner()
		subsub1 = TestSuccessJobRunner()

		root_id = self.jid()
		sub1_id = self.jid()
		sub2_id = self.jid()
		subsub1_id = self.jid()

		# Add the jobs.
		self.manager.add_job(root_id, root)
		self.manager.add_job(sub1_id, sub1)
		self.manager.add_job(sub2_id, sub2)
		self.manager.add_job(subsub1_id, subsub1)

		# And then their relationships.
		self.manager.add_child_job(root_id, sub1_id)
		self.manager.add_child_job(sub1_id, subsub1_id)
		self.manager.add_child_job(root_id, sub2_id)

		# Start processing them.
		self.manager.evaluate()

		self.short_wait_hack()

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		if subsub1_status['state'] not in ['ABORTED', 'SUCCESS']:
			self.assertTrue(False, "Subsub1 not in one of expected states.")
		self.assertEquals(sub1_status['state'], 'ABORTED', "Sub 1 should have been aborted.")
		self.assertEquals(sub2_status['state'], 'FAILED', "Sub 2 should have failed.")
		self.assertEquals(root_status['state'], 'ABORTED', "Root should have been aborted.")

	def test_manager_abort_tree(self):
		# Test that a subtree aborts correctly.
		root = TestSuccessJobRunner()
		sub1 = TestSuccessJobRunner()
		sub2 = TestAbortJobRunner()
		subsub1 = TestSuccessJobRunner()

		root_id = self.jid()
		sub1_id = self.jid()
		sub2_id = self.jid()
		subsub1_id = self.jid()

		# Add the jobs.
		self.manager.add_job(root_id, root)
		self.manager.add_job(sub1_id, sub1)
		self.manager.add_job(sub2_id, sub2)
		self.manager.add_job(subsub1_id, subsub1)

		# And then their relationships.
		self.manager.add_child_job(root_id, sub1_id)
		self.manager.add_child_job(sub1_id, subsub1_id)
		self.manager.add_child_job(root_id, sub2_id)

		# Start processing them.
		self.manager.evaluate()

		# Wait for things to settle.
		self.short_wait_hack()

		# Abort Sub2, which should currently be holding everything up.
		self.manager.abort(sub2_id)

		# Wait for things to settle.
		self.short_wait_hack()

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status['state'], 'SUCCESS', "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status['state'], 'SUCCESS', "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status['state'], 'ABORTED', "Sub 2 should have been aborted.")
		self.assertEquals(root_status['state'], 'ABORTED', "Root should have been aborted.")

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.05, self.stop)
		self.wait()
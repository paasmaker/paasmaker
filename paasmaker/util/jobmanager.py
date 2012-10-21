
import uuid
import time
import paasmaker
from pubsub import pub
import tornado
import tornado.testing

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
		self.configuration = configuration
		# Map job_id => job
		self.jobs = {}
		# Map child_id => parent_id
		self.parents = {}
		if io_loop:
			self.io_loop = io_loop
		else:
			self.io_loop = tornado.ioloop.IOLoop.instance()

		pub.subscribe(self.job_status_change, 'job.status')

	def add_job(self, job_id, job):
		if not isinstance(job, JobRunner):
			raise ValueError("job parameter should be instance of JobRunner.")
		job.set_job_parameters(job_id, self)
		self.jobs[job_id] = job

	def add_child_job(self, parent_id, child_id):
		# TODO: more error checking/exceptions here.
		# TODO: Send audit updates with the parent/child relationship, and WAITING state.
		parent = self.jobs[parent_id]
		child = self.jobs[child_id]
		parent.add_child_job(child)
		self.parents[child_id] = parent_id

	def evaluate(self):
		# Evaluate and kick off any jobs that can be started now.
		for job_id, job in self.jobs.iteritems():
			if job.is_ready():
				# Do this on the IO loop, so it cooperates with everything else.
				self.io_loop.add_callback(job.start_job_helper)

	def finished(self, job_id, state, summary):
		# Pipe off this to any listeners who want to know.
		self.configuration.send_job_status(job_id, state=state, summary=summary)

	def abort(self, job_id, reason="Aborted"):
		# TODO: Find and kill the job.
		#self.finished(job_id, 'ABORTED', reason)
		pass

	def find_entire_subtree(self, parent):
		subtree = {}
		subtree.update(parent.job_children)
		for child_id, child in parent.job_children.iteritems():
			subtree.update(self.find_entire_subtree(child))
		return subtree

	def handle_fail(self, job_id):
		# Find the ultimate parent of this job.
		parent_id = job_id
		# TODO: Check if we even have this job.
		parent = self.jobs[job_id]
		while self.parents.has_key(parent_id):
			if self.jobs.has_key(parent_id):
				parent = self.jobs[self.parents[parent_id]]
				parent_id = parent.job_id

		# Now find the entire subtree for that job.
		subtree = self.find_entire_subtree(parent)
		subtree[parent.job_id] = parent

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

		# Now fail them all.
		for key, job in subtree.iteritems():
			if job.job_running:
				job.abort_job()
			# Mark it as aborted (in case it's on the IO loop awaiting startup)
			job.job_aborted = True
			# Send the status of aborted.
			self.finished(key, 'ABORTED', 'A related job failed or was aborted, so this job was aborted.')

	def job_status_change(self, job_id=None, state=None, source=None):
		# Not in our database? Do nothing.
		if not self.jobs.has_key(job_id):
			return

		# Handle the incoming states.
		if state in paasmaker.common.core.constants.JOB_ERROR_STATES:
			# That job failed, or was aborted. Kill off related jobs.
			self.handle_fail(job_id)

		if state in paasmaker.common.core.constants.JOB_SUCCESS_STATES:
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
		self.stop(kwargs)

	def wait_until_state(self, state, job_ids=[]):
		# See if it's one of our stored statuses.
		# This is to stop race conditions around the test.
		if len(job_ids) > 0:
			for jid in self.statuses.keys():
				if jid in job_ids and state == self.statuses[jid]['state']:
					return self.statuses[jid]

		# Now wait for the job like normal.
		result = self.wait()
		if len(job_ids) > 0:
			while not result and result['state'] != state and result['job_id'] not in job_ids:
				result = self.wait()
		else:
			while not result and result['state'] != state:
				result = self.wait()
		return result

	def jid(self):
		return str(uuid.uuid4())

	def test_manager_success_simple(self):
		# Set up a simple successful job.
		job_id = self.jid()
		job = TestSuccessJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		result = self.wait_until_state('SUCCESS')

		self.assertEquals(result['job_id'], job_id, 'Returned job was not expected job.')
		self.assertEquals(result['state'], 'SUCCESS', 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		job_id = self.jid()
		job = TestFailJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		result = self.wait_until_state('FAILED')

		self.assertEquals(result['job_id'], job_id, 'Returned job was not expected job.')
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

		# One of these two should finish.
		self.wait_until_state('SUCCESS', [subsub1_id, sub2_id])
		# Then one of these three.
		self.wait_until_state('SUCCESS', [sub1_id, sub2_id, subsub1_id])
		# Then one of these two.
		self.wait_until_state('SUCCESS', [sub1_id, sub2_id])
		# Then the root job.
		self.wait_until_state('SUCCESS', [root_id])

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

		#print
		#print "Root", root_id
		#print "Sub1", sub1_id
		#print "Sub2", sub2_id
		#print "Subsub1", subsub1_id

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

		# Subsub1 should succeed.
		self.wait_until_state('ABORTED', [subsub1_id])
		# But Sub2 should fail.
		self.wait_until_state('FAILED', [sub2_id])
		# Which will cause sub1 and the root to abort.
		self.wait_until_state('ABORTED', [sub1_id])
		# Then the root job.
		self.wait_until_state('ABORTED', [root_id])

	def test_manager_abort_tree(self):
		pass

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.1, self.stop)
		self.wait()
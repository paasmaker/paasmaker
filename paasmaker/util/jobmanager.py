
import uuid
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

	def add_child_job(self, job):
		self.job_children[job.job_id] = job
	def completed_child_job(self, job_id):
		if self.job_children.has_key(job_id):
			del self.job_children[job_id]

	def is_ready(self):
		return not self.job_running and len(self.job_children.keys()) == 0

	def start_job(self):
		raise NotImplementedError("Start is not implemented.")

	def abort_job(self):
		raise NotImplementedError("Abort is not implemented.")

	def start_job_helper(self):
		self.job_manager.configuration.send_job_status(self.job_id, state='RUNNING')
		self.start_job()

	def finished_job(self, state, summary):
		self.job_manager.finished(self.job_id, state, summary)

	def aborted_job(self, summary):
		self.finished_job('ABORTED', summary)

	def job_logger(self):
		if self.job_cached_logger:
			return self.job_cached_logger

		self.job_cached_logger = self.job_manager.configuration.get_job_logger(self.job_id)

		return self.job_cached_logger

class JobManager(object):
	def __init__(self, configuration, io_loop=None):
		self.configuration = configuration
		self.jobs = {}
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
		parent = self.jobs[parent_id]
		child = self.jobs[child_id]
		parent.add_child_job(child)
		self.parents[child_id] = parent_id

	def evaluate(self):
		# Evaluate and kick off any jobs that can be started now.
		for job_id, job in self.jobs.iteritems():
			if job.is_ready():
				# Do this on the IO loop, so it cooperates with everything else.
				job.job_running = True
				self.io_loop.add_callback(job.start_job_helper)

	def finished(self, job_id, state, summary):
		# Pipe off this to any listeners who want to know.
		self.configuration.send_job_status(job_id, state=state, summary=summary)

	def abort(self, job_id, reason="Aborted"):
		# TODO: Find and kill the job.
		#self.finished(job_id, 'ABORTED', reason)
		pass

	def job_status_change(self, job_id=None, state=None, source=None):
		# Handle the incoming states.
		if state in paasmaker.common.core.constants.JOB_ERROR_STATES:
			# That job failed. Kill off related jobs.
			# TODO: Implement.
			pass
		if state in paasmaker.common.core.constants.JOB_SUCCESS_STATES:
			# Success! Mark it as complete, then evaluate our jobs again.
			# Does this job have a parent? If so, remove this job from
			# the list, so it goes on to process the next one.
			if self.parents.has_key(job_id):
				parent_id = self.parents[job_id]
				parent = self.jobs[parent_id]
				parent.completed_child_job(job_id)
				del self.parents[job_id]
			if self.jobs.has_key(job_id):
				del self.jobs[job_id]

		# Now evaluate jobs and take the appropriate actions.
		self.evaluate()

class TestSuccessJobRunner(JobRunner):
	def start_job(self):
		self.finished_job('SUCCESS', "Completed successfully.")

class TestFailJobRunner(JobRunner):
	def start_job(self):
		self.finished_job('FAILED', "Failed to complete.")

class TestAbortJobRunner(JobRunner):
	def start_job(self):
		# Do nothing. In theory, we're now running.
		pass

	def abort_job(self):
		self.aborted_job("Job was aborted.")

class JobManagerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(JobManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'])
		self.configuration.set_node_uuid('test')
		self.manager = JobManager(self.configuration, self.io_loop)
		pub.subscribe(self.on_job_status, 'job.status')
		self.statuses = {}

	def tearDown(self):
		self.configuration.cleanup()
		pub.unsubscribe(self.on_job_status, 'job.status')
		super(JobManagerTest, self).tearDown()

	def on_job_status(self, **kwargs):
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
			while result['state'] != state and result['job_id'] not in job_ids:
				result = self.wait()
		else:
			while result['state'] != state:
				result = self.wait()
		return result

	def test_manager_success_simple(self):
		# Set up a simple successful job.
		job_id = str(uuid.uuid4())
		job = TestSuccessJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		result = self.wait_until_state('SUCCESS')

		self.assertEquals(result['job_id'], job_id, 'Returned job was not expected job.')
		self.assertEquals(result['state'], 'SUCCESS', 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		job_id = str(uuid.uuid4())
		job = TestFailJobRunner()
		self.manager.add_job(job_id, job)

		self.manager.evaluate()

		result = self.wait_until_state('FAILED')

		self.assertEquals(result['job_id'], job_id, 'Returned job was not expected job.')
		self.assertEquals(result['state'], 'FAILED', 'Test job was not a failure.')

	def test_manager_success_tree(self):
		def jid():
			return str(uuid.uuid4())

		# Test that a subtree processes correctly.
		root = TestSuccessJobRunner()
		sub1 = TestSuccessJobRunner()
		sub2 = TestSuccessJobRunner()
		subsub1 = TestSuccessJobRunner()

		root_id = jid()
		sub1_id = jid()
		sub2_id = jid()
		subsub1_id = jid()

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
		# TODO: Implement.
		pass

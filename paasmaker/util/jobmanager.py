
import uuid
import time
import logging
import json

import paasmaker
from plugin import MODE, Plugin
from paasmaker.common.core import constants
from ..common.testhelpers import TestHelpers

from pubsub import pub

import tornado
import tornado.testing

import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# TODO: To the job manager, add the ability to add jobs but not allow them to execute just yet.
# Almost like a transaction - this prevents us half adding a job tree and then having that kicked off
# part way through.

class BaseJobOptionsSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseJobParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

class BaseJob(Plugin):
	MODES = [MODE.JOB]
	OPTIONS_SCHEMA = BaseJobOptionsSchema()
	PARAMETERS_SCHEMA = {MODE.JOB: BaseJobParametersSchema()}

class JobBackend(object):
	def __init__(self, configuration):
		self.configuration = configuration

	def setup(self, callback):
		"""
		Setup anything you need, and call the callback when ready.
		"""
		raise NotImplementedError("You must implement setup().")

	def store_context(self, job_id, context, callback):
		"""
		Store the given context for the given job ID.
		Context is a dict of values, but may only be a partial
		update of values. job_id may not be the root job ID,
		so you should resolve that first. Calls the callback once complete.
		"""
		raise NotImplementedError("You must implement update_context().")

	def get_context(self, job_id, callback):
		"""
		Fetch all the context for the given job ID, and call
		the callback with it as a dict. job_id is resolved to the root
		first before querying the values.
		"""
		raise NotImplementedError("You must implement get_context().")

	def get_parent(self, job_id, callback):
		"""
		Fetch the parent of the given job. If the job is a parent job,
		return the same job ID. Calls the callback with the parent id.
		"""
		raise NotImplementedError("You must implement get_parent().")

	def get_root(self, job_id, callback):
		"""
		Fetch the root of the given job. Call the callback with the root
		job ID. If the called job_id is the root id, pass that to the
		callback.
		"""
		raise NotImplementedError("You must implement get_root().")

	def get_children(self, job_id, callback, state=None):
		"""
		Get all the direct children of the given job_id. Call the callback
		with a set of job ids that are the children. The result should
		be filtered by the state if supplied, which can be a single value
		or a set of values.
		"""
		raise NotImplementedError("You must implement get_children().")

	def exists(self, job_id, callback):
		"""
		Determine if a job exists. Call the callback with a boolean
		value that indicates if it does or doesn't exist.
		"""
		raise NotImplementedError("You must implement exists().")

	def add_job(self, node, job_id, parent_id, callback, **kwargs):
		"""
		Add a job with the given job_id, and the given parent_id. Parent
		might be none, indicating that this is a top level job.
		kwargs are parameters for this job, which should be stored as
		appropriate for this job. Callback will be called once the job
		is added.
		"""
		raise NotImplementedError("You must implement add_job().")

	def set_attr(self, job_id, attr, value, callback):
		"""
		Set the supplied attribute to the supplied value on the given
		job ID. Calls callback when complete.
		"""
		raise NotImplementedError("You must implement set_attr().")

	def get_attr(self, job_id, attr, callback):
		"""
		Get the supplied attribute from the given job. Calls the callback
		with the value of that attribute.
		"""
		raise NotImplementedError("You must implement get_attr().")

	def get_job(self, job_id, callback):
		"""
		Gets all the values for the given job. Calls the callback with
		a dict of values.
		"""
		raise NotImplementedError("You must implement get_job().")

	def get_jobs(self, jobs, callback):
		"""
		Get the data for all the given jobs in one go, calling the callback
		with a dict. The keys are the job ids and the values a map of data.
		"""
		raise NotImplementedError("You must implement get_jobs().")

	def tag_job(self, job_id, tag, callback):
		"""
		Tag a job with the given tag. If the supplied job_id isn't a root
		ID, find and tag that root ID instead.
		"""
		raise NotImplementedError("You must implement tag_job().")

	def find_by_tag(self, tag, callback, limit=None):
		"""
		Return a set of parent jobs by the given tag. Call the callback
		with a list of job ids that match - which should only ever be
		root jobs. If possible, sort the returned jobs by their time in
		reverse, so most recent jobs first. This is designed for the front
		end to be able to list jobs to display to users, not for locating
		jobs that are ready to run or other tasks.
		"""
		raise NotImplementedError("You must implement find_by_tag().")

	def get_ready_to_run(self, node, waiting_state, success_state, callback):
		"""
		Return a set of jobs that are ready to run for the given node.
		"Ready to run" is defined as jobs on the node who are currently in the
		waiting state, and whose children are all in the supplied success state.
		Call the callback with a set of jobs that match.
		"""
		raise NotImplementedError("You must implement get_jobs_in_state().")

class JobBackendRedis(JobBackend):
	"""
	This is a job backend that stores job state in Redis. It's trying to
	do some relational things with Redis. The model that it's using is described
	below to explain how it store and accesses data.

	The backend uses Redis's transactions, especially when updating related sets.
	Redis guarantees that everything happens in that section, which should cover
	off any consistency issues.

	Uppercase values in key are application supplied values.
	Key => Type - Description
	JOBID => HASH - Hold the job information, such as state and attributes.
	JOBID_context => HASH - Holds the job context (JOBID is always the root job.)
	JOBID_parent => STRING - Quick way to locate the parent of a job. Can be None.
	JOBID_root => STRING - Quick way to locate the root job for a parent. Will return
	  the same value as the JOBID if the job is a root job.
	JOBID_children => SET - Set of job IDs of children of that job.
	JOBID_children_STATE => SET - Set of job IDs that are children in that state. This
	  is a subset of JOBID_children.
	node_NODE => SET - Set of job IDs that are assigned to the given node.
	node_NODE_STATE => SET - Set of job IDs that are assigned to the given node,
	  in the given state. This is a subset of node_NODE.
	tag_TAG => ZSET - Set of job IDs that match the given tag. This is a sorted set so
	  we can quickly return the most recent jobs first. Note that only root jobs are
	  given tags.
	JOBID_tags => SET - for the job ID, a set of tags that it has applied to it. Designed
	  for future use to be able to remove tags when a job is removed.
	"""

	def setup(self, callback):
		self.setup_callback = callback
		# TODO: Pass a valid error callback here.
		self.configuration.get_jobs_redis(self.redis_ready, None)

	def redis_ready(self, client):
		self.redis = client
		self.setup_callback()

	def _to_json(self, values):
		out = {}
		for key, value in values.iteritems():
			out[key] = json.dumps(value)
		return out

	def _from_json(self, values):
		result = {}
		for key, value in values.iteritems():
			if value:
				result[key] = json.loads(value)
			else:
				result[key] = None
		return result

	def store_context(self, job_id, context, callback):
		def on_stored(result):
			callback()

		def on_found_root(root_id):
			self.redis.hmset("%s_context" % root_id, self._to_json(context), on_stored)

		self.get_root(job_id, on_found_root)

	def get_context(self, job_id, callback):
		def on_hgetall(values):
			callback(self._from_json(values))

		def on_found_root(root_id):
			self.redis.hgetall("%s_context" % root_id, on_hgetall)

		self.get_root(job_id, on_found_root)

	def get_parent(self, job_id, callback):
		def on_get(value):
			# If value is None, that means we have no parent.
			if not value:
				callback(job_id)
			else:
				callback(value)

		self.redis.get("%s_parent" % job_id, on_get)

	def get_root(self, job_id, callback):
		def on_get(value):
			callback(value)

		self.redis.get("%s_root" % job_id, on_get)

	def get_children(self, job_id, callback, state=None):
		if state:
			# Use the JOB_children_STATE quick lookup.
			sfilter = state
			if isinstance(state, basestring):
				sfilter = set()
				sfilter.add(state)

			def on_state_results(results):
				output = set()
				for result in results:
					output.update(result)
				callback(output)

			pipeline = self.redis.pipeline()
			for s in sfilter:
				pipeline.smembers("%s_children_%s" % (job_id, s))
			pipeline.execute(on_state_results)

		else:
			# Just fetch the children raw - so get all of them.
			def on_smembers(jobs):
				callback(jobs)

			self.redis.smembers("%s_children" % job_id, on_smembers)

	def exists(self, job_id, callback):
		def on_exists(result):
			callback(result)

		self.redis.exists(job_id, on_exists)

	def add_job(self, node, job_id, parent_id, callback, state, **kwargs):
		def on_complete(result):
			callback()

		def on_found_root(root_id):
			# Serialize all incoming values to JSON.
			kwargs['job_id'] = job_id
			kwargs['parent_id'] = parent_id
			kwargs['time'] = time.time()
			kwargs['node'] = node
			kwargs['state'] = state
			values = self._to_json(kwargs)

			# Now set up the transaction to insert it all.
			pipeline = self.redis.pipeline(True)
			# The core job.
			pipeline.hmset(job_id, values)
			# Insert it into the node state list.
			pipeline.sadd("node_%s" % node, job_id)
			# TODO: This will cause issues if the job already exists.
			pipeline.sadd("node_%s_%s" % (node, state), job_id)
			# Handle parent related activities.
			if parent_id:
				# Set the parent ID mapping.
				pipeline.set("%s_parent" % job_id, parent_id)
				# Update the parent to have this as a child.
				pipeline.sadd("%s_children" % parent_id, job_id)
				# Update the parent's state map.
				# TODO: This will cause issues if the job already exists.
				pipeline.sadd("%s_children_%s" % (parent_id, state), job_id)
				# And store the root ID.
				pipeline.set("%s_root" % job_id, root_id)
			else:
				# Set the root for this job to be this job.
				pipeline.set("%s_root" % job_id, job_id)

			# Execute the pipeline.
			pipeline.execute(on_complete)

		# Find the root of this parent, or otherwise this job is root.
		if parent_id:
			self.get_root(parent_id, on_found_root)
		else:
			on_found_root(job_id)

	def set_attr(self, job_id, attr, value, callback):
		def on_complete(result):
			callback()

		def on_got_current_state(job):
			new_state = value
			# Now, start a transaction to update the appropriate maps.
			pipeline = self.redis.pipeline(True)
			# Remove from the old state sets and add to new ones.
			pipeline.srem("%(node)s_%(state)s" % job, job_id)
			pipeline.sadd("%s_%s" % (job['node'], new_state), job_id)
			if job['parent_id']:
				pipeline.srem("%(parent_id)s_children_%(state)s" % job, job_id)
				pipeline.sadd("%s_children_%s" % (job['parent_id'], new_state), job_id)
			pipeline.execute(on_complete)

		if attr == 'state':
			# Update the state maps as well. To do this, we need to know
			# what the current state is.
			self.get_job(job_id, on_got_current_state)
		else:
			# Just go ahead and update it.
			encoded = self._to_json({attr: value})
			self.redis.hmset(job_id, encoded, on_complete)

	def get_attr(self, job_id, attr, callback):
		def on_hmget(values):
			decoded = self._from_json(values)
			if decoded.has_key(attr):
				callback(decoded[attr])
			else:
				callback(None)

		self.redis.hmget(job_id, attr, on_complete)

	def get_job(self, job_id, callback):
		def on_hgetall(values):
			callback(self._from_json(values))

		self.redis.hgetall(job_id, on_hgetall)

	def get_jobs(self, jobs, callback):
		def on_bulk_hmget(values):
			output = {}
			for result in values:
				decoded = self._from_json(result)
				output[decoded['job_id']] = decoded
			callback(output)

		pipeline = self.redis.pipeline()
		for job in jobs:
			pipeline.hgetall(job)
		pipeline.execute(on_bulk_hmget)

	def tag_job(self, job_id, tag, callback):
		def on_tagged(result):
			callback()

		def on_found_root(root_id):
			# Tag the job in forward and reverse, in a pipeline.
			# We do this in a transaction to make sure both sides
			# are updated.
			pipeline = self.redis.pipeline(True)
			pipeline.zadd("tag_%s" % tag, time.time(), root_id)
			pipeline.sadd("%s_tags" % root_id, tag)
			pipeline.execute(on_tagged)

		self.get_root(job_id, on_found_root)

	def find_by_tag(self, tag, callback, limit=None):
		def on_zrevrangebyscore(jobs):
			callback(jobs)

		self.redis.zrevrangebyscore("tag_%s" % tag, "+inf", "-inf", limit=limit, callback=on_zrevrangebyscore)

	def get_ready_to_run(self, node, waiting_state, success_state, callback):
		def on_count_sets(sets):
			# The passed result will have three values for each job.
			# The first is the job id. The second is the number of children.
			# And the third is the number of jobs in the given state.
			output = set()
			index = 0
			while index < len(sets):
				if sets[index + 1] == sets[index + 2]:
					output.add(self._from_json(sets[index])['job_id'])
				index += 3

			callback(output)

		def on_waiting_state(jobs):
			# For each of the waiting jobs, check the length of the children
			# jobs in the success state. If it matches the length of the children set,
			# then this job is ready to run.
			pipeline = self.redis.pipeline()
			for job in jobs:
				pipeline.hmget(job, ['job_id'])
				pipeline.scard("%s_children" % job)
				pipeline.scard("%s_children_%s" %(job, success_state))
			pipeline.execute(on_count_sets)

		# First step, get all the jobs on the node in the waiting state.
		self.redis.smembers("node_%s_%s" % (node, waiting_state), on_waiting_state)

class JobManagerBackendTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(JobManagerBackendTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.backend = JobBackendRedis(self.configuration)
		self.backend.setup(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(JobManagerBackendTest, self).tearDown()

	def test_simple(self):
		self.backend.add_job('here', 'root', None, self.stop, constants.JOB.WAITING)
		self.wait()
		self.backend.add_job('here', 'child1', 'root', self.stop, constants.JOB.WAITING)
		self.wait()
		self.backend.add_job('here', 'child2', 'root', self.stop, constants.JOB.RUNNING)
		self.wait()
		self.backend.add_job('here', 'child1_1', 'child1', self.stop, constants.JOB.RUNNING)
		self.wait()

		# Make sure a job exists.
		self.backend.exists('root', self.stop)
		status = self.wait()

		# Fetch a single job.
		self.backend.get_job('child1', self.stop)
		job = self.wait()

		self.assertEquals(job['job_id'], 'child1', "Return job was not as expected.")

		# Fetch multiple jobs in a batch.
		self.backend.get_jobs(['child1', 'child2'], self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 2, "Missing jobs.")
		self.assertTrue(jobs.has_key('child1'), "Missing child1.")
		self.assertEquals(jobs['child1']['job_id'], 'child1', "Child1 isn't child1.")
		self.assertTrue(jobs.has_key('child2'), "Missing child2.")
		self.assertEquals(jobs['child2']['job_id'], 'child2', "Child2 isn't child2.")

		# Find the root job of child1 and child1_1.
		self.backend.get_root('child1', self.stop)
		root = self.wait()
		self.assertEquals(root, 'root', 'Root is not root.')
		self.backend.get_root('child1_1', self.stop)
		root = self.wait()
		self.assertEquals(root, 'root', 'Root is not root.')

		# Check to see our children are valid.
		self.backend.get_children('root', self.stop)
		children = self.wait()

		self.assertIn('child1', children, "Missing expected child.")
		self.assertIn('child2', children, "Missing expected child.")
		self.assertNotIn('child1_1', children, "Unexpected child.")

		# Try again, but this time only get running/waiting children.
		self.backend.get_children('root', self.stop, constants.JOB.WAITING)
		children = self.wait()
		self.assertIn('child1', children, "Missing expected child.")
		self.assertEquals(len(children), 1, "Not the right number of children.")
		self.backend.get_children('root', self.stop, [constants.JOB.RUNNING])
		children = self.wait()
		self.assertIn('child2', children, "Missing expected child.")
		self.assertEquals(len(children), 1, "Not the right number of children.")

		# Store context on child1, which should really store it against the root.
		self.backend.store_context('child1', {'foo': 'bar'}, self.stop)
		self.wait()
		self.backend.get_context('root', self.stop)
		context = self.wait()

		self.assertTrue(context.has_key('foo'), "Missing context.")
		self.assertEquals(context['foo'], 'bar', "Context is incorrect.")

		# Fetch the context again, from child2. It should be identical.
		self.backend.get_context('child2', self.stop)
		context = self.wait()
		self.assertTrue(context.has_key('foo'), "Missing context.")
		self.assertEquals(context['foo'], 'bar', "Context is incorrect.")

		# Now add to the context on child2. Both keys should now be present.
		self.backend.store_context('child2', {'baz': 'foo'}, self.stop)
		self.wait()
		self.backend.get_context('root', self.stop)
		context = self.wait()

		self.assertTrue(context.has_key('foo'), "Missing context.")
		self.assertEquals(context['foo'], 'bar', "Context is incorrect.")
		self.assertTrue(context.has_key('baz'), "Missing context.")
		self.assertEquals(context['baz'], 'foo', "Context is incorrect.")

		# Now we're going to tag child1_1. When we query it, we should get
		# the root job back.
		self.backend.tag_job('child1_1', 'workspace:1', self.stop)
		self.wait()
		self.backend.find_by_tag('workspace:1', self.stop)
		tagged_jobs = self.wait()

		self.assertIn('root', tagged_jobs, "Missing root job.")
		self.assertEquals(len(tagged_jobs), 1, "Too many jobs returned.")

		# Try querying child_1 again, but limit it to a given state.
		self.backend.find_by_tag('workspace:1', self.stop)
		tagged_jobs = self.wait()

		self.assertIn('root', tagged_jobs, "Missing root job.")
		self.assertEquals(len(tagged_jobs), 1, "Too many jobs returned.")

		#### MODIFY JOBS
		# Find jobs ready to run. Initially, this will be nothing.
		self.backend.get_ready_to_run('here', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 0, "Ready jobs when there should not have been.")

		# Mark child1_1 as complete.
		self.backend.set_attr('child1_1', 'state', constants.JOB.SUCCESS, self.stop)
		self.wait()
		# Make sure that it doesn't appear in RUNNING state in the children of child1.
		# (This could be caused by an error updating everything in the backend)
		self.backend.get_children('child1', self.stop, [constants.JOB.RUNNING])
		children = self.wait()
		self.assertEquals(len(children), 0, "Child1's children was not updated correctly.")
		self.backend.get_children('child1', self.stop, [constants.JOB.SUCCESS])
		children = self.wait()
		self.assertEquals(len(children), 1, "Child1's children was not updated correctly.")
		self.assertIn('child1_1', children, "Child1's children was not updated correctly.")

		# Now, if we find all jobs ready to run on the node, child1 should pop out.
		self.backend.get_ready_to_run('here', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()
		self.assertEquals(len(jobs), 1, "Not the right number of ready jobs.")
		self.assertIn('child1', jobs, "Child1 isn't ready.")

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
		# CAUTION: TODO: Not for subclass use. Move it.
		self.job_children[job.job_id] = job

	def completed_child_job(self, job_id):
		# CAUTION: TODO: Not for subclass use. Move it.
		if self.job_children.has_key(job_id):
			del self.job_children[job_id]

	def get_job_title(self):
		return "Unknown job title"

	def get_root_job(self):
		# NOTE: May return this object.
		return self.job_manager.get_root(self.job_id)

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
		if not self.job_aborted and not self.job_running:
			self.job_running = True
			self.job_manager.configuration.send_job_status(self.job_id, state=constants.JOB.RUNNING)
			# TODO: Catch sub exceptions, abort/fail job.
			self.start_job()

	def finished_job(self, state, summary):
		self.job_manager.finished(self.job_id, state, summary)

	def aborted_job(self, summary):
		self.job_aborted = True
		self.finished_job(constants.JOB.ABORTED, summary)

	def job_logger(self):
		if self.job_cached_logger:
			return self.job_cached_logger

		self.job_cached_logger = self.job_manager.configuration.get_job_logger(self.job_id)

		return self.job_cached_logger

class ContainerJob(JobRunner):
	# This is a super container for other jobs, that just succeeds when all of it's children succeed.
	# You can subclass it to store state for your job tree. (A bit of a hack...)
	def start_job(self):
		self.finished_job(constants.JOB.SUCCESS, "Completed successfully.")

	def abort_job(self):
		pass

class JobManager(object):
	def __init__(self, configuration, io_loop=None):
		logger.debug("Initialising JobManager.")
		self.configuration = configuration
		# Map job_id => job
		self.jobs = {}
		# Map child_id => parent_id
		self.parents = {}

		# Select an appropriate IO loop.
		if io_loop:
			logger.debug("Using supplied IO loop.")
			self.io_loop = io_loop
		else:
			logger.debug("Using global IO loop.")
			self.io_loop = tornado.ioloop.IOLoop.instance()

		logger.debug("Subscribing to job status updates.")
		pub.subscribe(self.job_status_change, 'job.status')

	def add_job(self, job, job_id=None):
		if not job_id:
			job_id = self.configuration.make_job_id(job.get_job_title())
		logger.info("Adding job object for %s", job_id)
		if not isinstance(job, JobRunner):
			raise ValueError("job parameter should be instance of JobRunner.")
		if hasattr(job, 'job_id'):
			if self.jobs.has_key(job.job_id):
				raise ValueError("This job already exists in this database. Don't readd it.")
		job.set_job_parameters(job_id, self)
		self.jobs[job_id] = job
		logger.debug("Job %s is now stored.", job_id)

	def add_child_job(self, parent, child):
		if not self.jobs.has_key(parent.job_id):
			raise KeyError("No such parent job %s" % parent.job_id)
		if not self.jobs.has_key(child.job_id):
			raise KeyError("No such child job %s" % child.job_id)
		logger.info("Parent %s adding child %s", parent.job_id, child.job_id)
		parent = self.jobs[parent.job_id]
		child = self.jobs[child.job_id]
		parent.add_child_job(child)
		self.parents[child.job_id] = parent.job_id
		logger.debug("Parent %s adding child %s complete.", parent.job_id, child.job_id)

		# Advertise that the job is now waiting, and the parent/child relationship.
		# TODO: Test this. Probably via the audit writer?
		self.configuration.send_job_status(child.job_id, state='WAITING', parent_id=parent.job_id)

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

		logger.info("Started %d (of %d) jobs this evaluation.", started_count, len(self.jobs))
		return started_count

	def finished(self, job_id, state, summary):
		# Pipe off this to any listeners who want to know.
		logger.info("Signalling finished for job %s with state %s", job_id, state)
		self.configuration.send_job_status(job_id, state=state, summary=summary)

	def abort(self, job_id, reason="Aborted by user or system request."):
		# Just signal that it's done. The callback will clean them all up.
		logger.info("Signalling abort for job %s.", job_id)
		self.finished(job_id, constants.JOB.ABORTED, reason)

	def find_entire_subtree(self, parent):
		subtree = {}
		subtree.update(parent.job_children)
		for child_id, child in parent.job_children.iteritems():
			subtree.update(self.find_entire_subtree(child))
		return subtree

	def get_root(self, job_id):
		parent_id = job_id
		# TODO: Check if we even have this job.
		parent = self.jobs[job_id]
		while self.parents.has_key(parent_id):
			if self.jobs.has_key(parent_id):
				parent = self.jobs[self.parents[parent_id]]
				parent_id = parent.job_id

		return parent

	def handle_fail(self, job_id):
		logger.debug("Handling failure for job id %s", job_id)
		# Find the ultimate parent of this job.
		parent = self.get_root(job_id)

		logger.debug("Ultimate parent of %s is %s.", job_id, parent.job_id)

		# Now find the entire subtree for that job.
		subtree = self.find_entire_subtree(parent)
		subtree[parent.job_id] = parent

		logger.debug("Found %d jobs in subtree for ultimate parent %s (source job %s)", len(subtree), parent.job_id, job_id)

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
			self.finished(key, constants.JOB.ABORTED, 'A related job failed or was aborted, so this job was aborted.')

		logger.debug("Subtree aborted (source job %s)", job_id)

	def job_status_change(self, message):
		job_id = message.job_id
		state = message.state

		# Not in our database? Do nothing.
		if not self.jobs.has_key(job_id):
			logger.debug("Got message for job that's not in our database - job %s", job_id)
			return

		# Handle the incoming states.
		if state in constants.JOB_ERROR_STATES:
			logger.info("Job %s in state %s - handling failure.", job_id, state)
			job = self.jobs[job_id]
			logger.info("Failed job: %s", job.get_job_title())
			# That job failed, or was aborted. Kill off related jobs.
			self.handle_fail(job_id)

		if state in constants.JOB_SUCCESS_STATES:
			logger.info("Job %s in state %s - evaluating new jobs for startup.", job_id, state)
			job = self.jobs[job_id]
			logger.info("Completed job: %s", job.get_job_title())
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
		self.finished_job(constants.JOB.SUCCESS, "Completed successfully.")

	def abort_job(self):
		pass

class TestFailJobRunner(JobRunner):
	def start_job(self):
		self.finished_job(constants.JOB.FAILED, "Failed to complete.")

	def abort_job(self):
		pass

class TestAbortJobRunner(JobRunner):
	def start_job(self):
		# Do nothing. In theory, we're now running.
		pass

	def abort_job(self):
		# Do something?
		pass

class JobManagerTest(tornado.testing.AsyncTestCase, TestHelpers):
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

	def on_job_status(self, message):
		#print str(message)
		# TODO: This storage overwrites the previous state. But I guess we're
		# generally waiting for it to end up in a particular end state...
		self.statuses[message.job_id] = message

	def get_state(self, job_id):
		if self.statuses.has_key(job_id):
			return self.statuses[job_id]
		else:
			return paasmaker.common.configuration.JobStatusMessage(job_id, 'UNKNOWN', None)

	def jid(self):
		return str(uuid.uuid4())

	def test_manager_success_simple(self):
		# Set up a simple successful job.
		job_id = self.jid()
		job = TestSuccessJobRunner()
		self.manager.add_job(job, job_id)

		self.manager.evaluate()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result.state, constants.JOB.SUCCESS, 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		job_id = self.jid()
		job = TestFailJobRunner()
		self.manager.add_job(job, job_id)

		self.manager.evaluate()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result.state, constants.JOB.FAILED, 'Test job was not a failure.')

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
		self.manager.add_job(root, root_id)
		self.manager.add_job(sub1, sub1_id)
		self.manager.add_job(sub2, sub2_id)
		self.manager.add_job(subsub1, subsub1_id)

		# And then their relationships.
		self.manager.add_child_job(root, sub1)
		self.manager.add_child_job(sub1, subsub1)
		self.manager.add_child_job(root, sub2)

		# Start processing them.
		self.manager.evaluate()

		self.short_wait_hack()

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status.state, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status.state, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status.state, constants.JOB.SUCCESS, "Sub 2 should have succeeded.")
		self.assertEquals(root_status.state, constants.JOB.SUCCESS, "Root should have succeeded.")

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
		self.manager.add_job(root, root_id)
		self.manager.add_job(sub1, sub1_id)
		self.manager.add_job(sub2, sub2_id)
		self.manager.add_job(subsub1, subsub1_id)

		# And then their relationships.
		self.manager.add_child_job(root, sub1)
		self.manager.add_child_job(sub1, subsub1)
		self.manager.add_child_job(root, sub2)

		# Start processing them.
		self.manager.evaluate()

		self.short_wait_hack()

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		if subsub1_status.state not in [constants.JOB.ABORTED, constants.JOB.SUCCESS]:
			self.assertTrue(False, "Subsub1 not in one of expected states.")
		self.assertEquals(sub1_status.state, constants.JOB.ABORTED, "Sub 1 should have been aborted.")
		self.assertEquals(sub2_status.state, constants.JOB.FAILED, "Sub 2 should have failed.")
		self.assertEquals(root_status.state, constants.JOB.ABORTED, "Root should have been aborted.")

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
		self.manager.add_job(root, root_id)
		self.manager.add_job(sub1, sub1_id)
		self.manager.add_job(sub2, sub2_id)
		self.manager.add_job(subsub1, subsub1_id)

		# And then their relationships.
		self.manager.add_child_job(root, sub1)
		self.manager.add_child_job(sub1, subsub1)
		self.manager.add_child_job(root, sub2)

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

		self.assertEquals(subsub1_status.state, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status.state, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status.state, constants.JOB.ABORTED, "Sub 2 should have been aborted.")
		self.assertEquals(root_status.state, constants.JOB.ABORTED, "Root should have been aborted.")
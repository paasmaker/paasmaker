
import time
import json
import uuid
import logging

import paasmaker
from ...testhelpers import TestHelpers
from paasmaker.common.core import constants
from backend import JobBackend

from pubsub import pub
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RedisJobBackend(JobBackend):
	"""
	This is a job backend that stores job state in Redis. It's trying to
	do some relational things with Redis. The model that it's using is described
	below to explain how it store and accesses data.

	The backend uses Redis's transactions, especially when updating related sets.
	Redis guarantees that everything happens in that section, which should cover
	off any consistency issues.

	Key => Type
		Description
	<JOBID> => HASH
		Hold the job information, such as state and attributes.
	<JOBID>:context => HASH
		Holds the job context (JOBID is always the root job.)
	<JOBID>:parent => STRING
		Quick way to locate the parent of a job. Can be None.
	<JOBID>:root => STRING
		Quick way to locate the root job for a parent. Will return
		the same value as the JOBID if the job is a root job.
	<JOBID>:children => SET
		Set of job IDs of children of that job.
	<JOBID>:children:<STATE> => SET
		Set of job IDs that are children in that state. This
		is a subset of <JOBID>:children.
	<ROOTID>:tree => SET
		Set of all jobs under the root job.
	<ROOTID>:tree:<STATE> => SET
		Set of all jobs under the root job in the given state.
	node:<NODE> => SET
		Set of job IDs that are assigned to the given node.
	node:<NODE>:<STATE> => SET
		Set of job IDs that are assigned to the given node,
		in the given state. This is a subset of node:<NODE>.
	tag:<TAG> => ZSET
		Set of job IDs that match the given tag. This is a sorted set so
		we can quickly return the most recent jobs first. Note that only root jobs are
		given tags.
	<JOBID>:tags => SET
		For the job ID, a set of tags that it has applied to it. Designed
		to be able to remove tags when a job is removed.
	roots => ZSET
		A set of all root jobs, sorted by their timestamp. Used to locate old
		jobs for removal.
	"""

	def setup(self, callback, error_callback):
		self.setup_callback = callback
		self.setup_steps = 2

		if not hasattr(self, 'pubsub_internal_subscribed'):
			self.pubsub_internal_subscribed = False

		if not hasattr(self, 'redis'):
			self.redis = None
		if not hasattr(self, 'pubsub_client'):
			self.pubsub_client = None

		if self.redis is None or not self.redis.connection.connected():
			self.configuration.get_jobs_redis(self.redis_ready, error_callback)
		if self.pubsub_client is None or not self.pubsub_client.connection.connected():
			self.configuration.get_jobs_redis(self.pubsub_redis_ready, error_callback)

	def redis_ready(self, client):
		self.redis = client
		self.setup_steps -= 1
		self.check_setup_complete()

	def pubsub_redis_ready(self, client):
		self.pubsub_client = client

		# Subscribe to the job status channel.
		def on_subscribed(result):
			# Set up the listen handler.
			self.pubsub_client.listen(self._on_job_status_message)
			# Listen to internally published messages.
			# But don't do it on connection failure/reconnection.
			if not self.pubsub_internal_subscribed:
				pub.subscribe(self.send_job_status, 'job.status')
				self.pubsub_internal_subscribed = False
			# And signal completion.
			self.setup_steps -= 1
			self.check_setup_complete()

		self.pubsub_client.subscribe('job.status', on_subscribed)

	def check_setup_complete(self):
		if self.setup_steps == 0:
			self.setup_callback("Jobs backend Redis ready.")

	def ensure_connected(self):
		reconnection_required = False

		# If the redis/pubsub_client are None, we never connected.
		if self.redis is None or self.pubsub_client is None:
			reconnection_required = True
		elif not self.redis.connection.connected():
			reconnection_required = True
		elif not self.pubsub_client.connection.connected():
			reconnection_required = True

		if reconnection_required:
			def reconnect_success(message):
				# Reconnected successfully.
				logger.info("Successfully reconnected to the jobs Redis system.")
				logger.info("Will start evaluating jobs.")
				# Trigger off any pending jobs.
				self.configuration.job_manager.evaluate()

			def reconnect_failed(message, exception=None):
				# Failed.
				# Make an obvious warning in the logs that we're out of touch.
				logger.error("UNABLE TO RECONNECT TO JOBS REDIS.")
				logger.error(message)
				if exception:
					logger.error("Exception", exc_info=exception)
				logger.error("SHOULD ATTEMPT AGAIN SHORTLY.")

			logger.error("NOT CONNECTED TO JOBS BACKEND REDIS.")
			logger.error("REATTEMPTING CONNECTION.")
			self.setup(reconnect_success, reconnect_failed)
		else:
			logger.debug("Job manager is still connected.")

	def _on_job_status_message(self, message):
		if isinstance(message.body, int):
			# It's a subscribed count. Ignore.
			return

		# TODO: Handle parse failures and other related issues.
		parsed = json.loads(str(message.body))

		if parsed['source'] == self.configuration.get_node_uuid():
			# It's a message from us. drop it.
			logger.debug("Dropping status message %s because it originated from us.", str(message.body))
		else:
			logger.debug("Got job status message: %s", str(message.body))
			self.configuration.send_job_status(
				parsed['job_id'],
				state=parsed['state'],
				source=parsed['source'],
				summary=parsed['summary'],
				parent_id=parsed['parent_id']
			)

	def send_job_status(self, message):
		if not hasattr(message, 'unittest_override'):
			if message.source != self.configuration.get_node_uuid():
				logger.debug("Not sending message for job %s because it's from some other node." % message.job_id)
				return
		else:
			logger.debug("Unit test override - forcing send of message via pub sub.")

		body = message.flatten()
		encoded = json.dumps(body)
		logger.debug("Sending job status message: %s", encoded)
		try:
			self.redis.publish('job.status', encoded)
		except ValueError, ex:
			# TODO: React to this situation. It's caused by the redis connection being closed.
			# TODO: This will bite later!
			logger.error("Unable to send job status via Redis: ", exc_info=ex)

	def _to_json(self, values):
		out = {}
		for key, value in values.iteritems():
			out[key] = json.dumps(value, cls=paasmaker.util.jsonencoder.JsonEncoder)
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
			self.redis.hmset("%s:context" % root_id, self._to_json(context), on_stored)

		self.get_root(job_id, on_found_root)

	def get_context(self, job_id, callback):
		def on_hgetall(values):
			callback(self._from_json(values))

		def on_found_root(root_id):
			self.redis.hgetall("%s:context" % root_id, on_hgetall)

		self.get_root(job_id, on_found_root)

	def get_parent(self, job_id, callback):
		def on_get(value):
			# If value is None, that means we have no parent.
			if not value:
				callback(job_id)
			else:
				callback(value)

		self.redis.get("%s:parent" % job_id, on_get)

	def get_root(self, job_id, callback):
		def on_get(value):
			callback(value)

		self.redis.get("%s:root" % job_id, on_get)

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
				pipeline.smembers("%s:children:%s" % (job_id, s))
			pipeline.execute(on_state_results)

		else:
			# Just fetch the children raw - so get all of them.
			def on_smembers(jobs):
				callback(jobs)

			self.redis.smembers("%s:children" % job_id, on_smembers)

	def exists(self, job_id, callback):
		def on_exists(result):
			callback(result)

		self.redis.exists(job_id, on_exists)

	def add_job(self, node, job_id, parent_id, callback, state, **kwargs):
		# Make a note of the tags.
		tags = []
		if kwargs.has_key('tags') and kwargs['tags']:
			tags = kwargs['tags']
			del kwargs['tags']

		def on_really_complete(result=None):
			callback()

		def on_complete(result):
			if len(tags) > 0:
				# Add tags.
				self.tag_job(job_id, tags, on_really_complete)
			else:
				on_really_complete()

		def on_found_root(root_id):
			# Serialize all incoming values to JSON.
			kwargs['job_id'] = job_id
			kwargs['parent_id'] = parent_id
			kwargs['root_id'] = root_id
			kwargs['time'] = time.time()
			kwargs['node'] = node
			kwargs['state'] = state
			values = self._to_json(kwargs)

			# Now set up the transaction to insert it all.
			pipeline = self.redis.pipeline(True)
			# The core job.
			pipeline.hmset(job_id, values)
			# Insert it into the node state list.
			pipeline.sadd("node:%s" % node, job_id)
			# TODO: This will cause issues if the job already exists.
			pipeline.sadd("node:%s:%s" % (node, state), job_id)
			# Handle parent related activities.
			if parent_id:
				# Set the parent ID mapping.
				pipeline.set("%s:parent" % job_id, parent_id)
				# Update the parent to have this as a child.
				pipeline.sadd("%s:children" % parent_id, job_id)
				# Update the parent's state map.
				# TODO: This will cause issues if the job already exists.
				pipeline.sadd("%s:children:%s" % (parent_id, state), job_id)

			# And store the root ID.
			pipeline.set("%s:root" % job_id, root_id)
			# Store on the root job lists.
			pipeline.sadd("%s:tree" % root_id, job_id)
			# TODO: This will cause issues if the job already exists.
			pipeline.sadd("%s:tree:%s" % (root_id, state), job_id)
			# Add the root job to the set of root jobs.
			pipeline.zadd("roots", time.time(), root_id)

			# Execute the pipeline.
			pipeline.execute(on_complete)

		# Find the root of this parent, or otherwise this job is root.
		if parent_id:
			self.get_root(parent_id, on_found_root)
		else:
			on_found_root(job_id)

	def set_attrs(self, job_id, attrs, callback):
		def on_complete(result):
			# The last result is the whole job object.
			job_data = self._from_json(result[-1])
			callback(job_data)

		def on_got_current_state(job):
			new_state = attrs['state']
			# Now, start a transaction to update the appropriate maps.
			pipeline = self.redis.pipeline(True)
			# Remove from the old state sets and add to new ones.
			pipeline.srem("node:%(node)s:%(state)s" % job, job_id)
			pipeline.sadd("node:%s:%s" % (job['node'], new_state), job_id)
			if job['parent_id']:
				pipeline.srem("%(parent_id)s:children:%(state)s" % job, job_id)
				pipeline.sadd("%s:children:%s" % (job['parent_id'], new_state), job_id)
			pipeline.srem("%(root_id)s:tree:%(state)s" % job, job_id)
			pipeline.sadd("%s:tree:%s" % (job['root_id'], new_state), job_id)
			encoded = self._to_json(attrs)
			pipeline.hmset(job_id, encoded)
			pipeline.hgetall(job_id)
			pipeline.execute(on_complete)

		if attrs.has_key('state'):
			# Update the state maps as well. To do this, we need to know
			# what the current state is.
			self.get_job(job_id, on_got_current_state)
		else:
			# Just go ahead and update it.
			encoded = self._to_json(attrs)
			pipeline = self.redis.pipeline(True)
			pipeline.hmset(job_id, encoded)
			pipeline.hgetall(job_id)
			pipeline.execute(on_complete)

	def get_attr(self, job_id, attr, callback):
		def on_hmget(values):
			decoded = self._from_json(values)
			if decoded.has_key(attr):
				callback(decoded[attr])
			else:
				callback(None)

		self.redis.hmget(job_id, [attr], on_hmget)

	def get_job(self, job_id, callback):
		def on_hgetall(values):
			callback(self._from_json(values))

		self.redis.hgetall(job_id, on_hgetall)

	def get_jobs(self, jobs, callback):
		def on_bulk_hmget(values):
			output = {}
			for result in values:
				decoded = self._from_json(result)
				if decoded.has_key('job_id'):
					# If it's missing this key, there is no such job.
					output[decoded['job_id']] = decoded
			callback(output)

		pipeline = self.redis.pipeline()
		for job in jobs:
			pipeline.hgetall(job)
		pipeline.execute(on_bulk_hmget)

	def tag_job(self, job_id, incoming_tag, callback):
		def on_tagged(result):
			callback()

		def on_found_root(root_id):
			# Tag the job in forward and reverse, in a pipeline.
			# We do this in a transaction to make sure both sides
			# are updated.
			if isinstance(incoming_tag, basestring):
				tags = [incoming_tag]
			else:
				tags = list(incoming_tag)

			pipeline = self.redis.pipeline(True)
			for tag in tags:
				pipeline.zadd("tag:%s" % tag, time.time(), root_id)
				pipeline.sadd("%s:tags" % root_id, tag)
			pipeline.execute(on_tagged)

		self.get_root(job_id, on_found_root)

	def find_by_tag(self, tag, callback, limit=None):
		def on_zrevrangebyscore(jobs):
			callback(jobs)

		offset = None
		if limit:
			offset = 0

		self.redis.zrevrangebyscore("tag:%s" % tag, "+inf", "-inf", offset=offset, limit=limit, callback=on_zrevrangebyscore)

	def find_older_than(self, age, callback, limit=None):
		def on_zrevrangebyscore(jobs):
			callback(jobs)

		offset = None
		if limit:
			offset = 0

		self.redis.zrevrangebyscore("roots", age, "-inf", offset=offset, limit=limit, callback=on_zrevrangebyscore)

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
				pipeline.scard("%s:children" % job)
				pipeline.scard("%s:children:%s" %(job, success_state))
			pipeline.execute(on_count_sets)

		# First step, get all the jobs on the node in the waiting state.
		self.redis.smembers("node:%s:%s" % (node, waiting_state), on_waiting_state)

	def set_state_tree(self, job_id, from_state, to_state, callback, node=None):
		def on_found_tree(tree):
			treecopy = set(tree)
			# We're going to do this the slow way, calling each one in turn.
			# TODO: Think about the transactional issues surrounding this.
			def process_job(data):
				try:
					job = treecopy.pop()
					self.set_attrs(job, {'state': to_state}, process_job)
				except KeyError, ex:
					# No more elements.
					# We're done.
					callback(tree)

			# Kick off the process.
			process_job(None)

		def on_found_root(root_id):
			if not node:
				# Get the whole root tree.
				self.redis.smembers("%s:tree:%s" % (root_id, from_state), on_found_tree)
			else:
				# Get the ones for this node - that is the intersection
				# between jobs on our node in that state and the jobs in
				# that tree.
				self.redis.sinter(["%s:tree:%s" % (root_id, from_state), "node:%s:%s" % (node, from_state)], on_found_tree)

		self.get_root(job_id, on_found_root)

	def get_tree(self, job_id, callback, state=None, node=None):
		# State Node Source
		# None  None  [root tree] SET
		# []    None  [root tree in states] UNION
		# None  str   Intersect [root tree] and [node list]. SET SET
		# []    str   Intersect [root tree in states] and [node list] UNION SET
		def on_completed(result):
			callback(result[-3])

		def on_found_root(root_id):
			state_sets = []
			state_set_name = "temp_state:" + str(uuid.uuid4())
			result_set_name = "temp_result:" + str(uuid.uuid4())
			if state:
				# Assemble the states into a set of sets that
				# contain the desired states.
				sfilter = state
				if isinstance(state, basestring):
					sfilter = set()
					sfilter.add(state)

				for s in sfilter:
					state_sets.append("%s:tree:%s" % (root_id, s))
			else:
				# Just use the raw set.
				state_sets.append("%s:tree" % root_id)

			# Now, start a transaction.
			pipeline = self.redis.pipeline(True)
			# Select all those sets into the temporary set.
			pipeline.sunionstore(state_sets, state_set_name)
			# Now, if we have a node, intersect that and store it.
			if node:
				pipeline.sinterstore([state_set_name, "node:%s" % node], result_set_name)
			else:
				result_set_name = state_set_name
			# Fetch out the result set.
			pipeline.smembers(result_set_name)
			pipeline.delete(result_set_name)
			pipeline.delete(state_set_name)
			pipeline.execute(on_completed)

		self.get_root(job_id, on_found_root)

	def delete_tree(self, job_id, callback):
		def on_found_root(root_id):
			def on_root_tags(root_tags):
				def on_completed(result):
					callback()
					# end of on_completed()

				def on_all_jobs(all_jobs):
					# Start removing all entries.
					pipeline = self.redis.pipeline(True)

					for child_id, metadata in all_jobs.iteritems():
						node_id = metadata['node']

						pipeline.delete(child_id)
						pipeline.delete("%s:context" % child_id)
						pipeline.delete("%s:parent" % child_id)
						pipeline.delete("%s:root" % child_id)
						pipeline.delete("%s:children" % child_id)
						pipeline.srem("node:%s" % node_id, child_id)
						for state in constants.JOB.ALL:
							pipeline.delete("%s:children:%s" % (child_id, state))
							pipeline.srem("node:%s:%s" % (node_id, state), child_id)

					# Now for the root job.
					for tag in root_tags:
						pipeline.zrem("tag:%s" % tag, root_id)

					pipeline.zrem("roots", root_id)
					pipeline.execute(on_completed)

				def on_found_tree(tree):
					# Find all metadata for the jobs.
					self.get_jobs(tree, on_all_jobs)
					# end of on_found_tree()

				self.get_tree(root_id, on_found_tree)
				# end of on_root_tags()

			# Fetch the root node tags.
			self.redis.smembers("%s:tags" % root_id, callback=on_root_tags)
			# end of on_found_root()

		# Find the root of the job.
		self.get_root(job_id, on_found_root)

	def get_node_jobs(self, node, callback, state=None):
		# Figure out what sets to fetch from.
		sets = []
		if state:
			if isinstance(state, basestring):
				sets.append("node:%s:%s" % (node, state))
			else:
				for state_name in state:
					sets.append("node:%s:%s" % (node, state_name))
		else:
			sets.append("node:%s" % node)

		def got_node_jobs(jobs):
			callback(jobs)

		# Now fetch the intersection of those sets.
		self.redis.sunion(sets, callback=got_node_jobs)

class JobManagerBackendTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(JobManagerBackendTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		# TODO: This only tests the redis backend. But in future,
		# all backends should be testable with exactly the same
		# unit tests as shown here.
		self.backend = RedisJobBackend(self.configuration)
		self.backend.setup(self.stop, self.stop)
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

		# Find all the jobs older than... the future.
		self.backend.find_older_than(time.time() + 10, self.stop)
		older = self.wait()

		self.assertEquals(len(older), 1, "Not the right number of older jobs.")

		self.backend.find_older_than(time.time() - 10, self.stop)
		older = self.wait()

		self.assertEquals(len(older), 0, "Not the right number of older jobs.")

		# Find all the jobs on the node.
		self.backend.get_node_jobs('here', self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 4, "Wrong number of node jobs returned.")

		# Find by state on the node.
		self.backend.get_node_jobs('here', self.stop, state=constants.JOB.RUNNING)
		jobs = self.wait()

		self.assertEquals(len(jobs), 2, "Wrong number of node jobs returned.")

		# Find by an array of states on the node.
		self.backend.get_node_jobs('here', self.stop, state=[constants.JOB.RUNNING])
		jobs = self.wait()

		self.assertEquals(len(jobs), 2, "Wrong number of node jobs returned.")

		self.backend.get_node_jobs('here', self.stop, state=[constants.JOB.RUNNING, constants.JOB.WAITING])
		jobs = self.wait()

		self.assertEquals(len(jobs), 4, "Wrong number of node jobs returned.")

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

		# Fetch the whole tree.
		self.backend.get_tree('child1', self.stop)
		tree = self.wait()
		self.assertEquals(len(tree), 4, "Failed to fetch the whole tree.")

		# Fetch the tree by state.
		self.backend.get_tree('child1', self.stop, state=constants.JOB.WAITING)
		tree = self.wait()
		self.assertEquals(len(tree), 2, "Failed to fetch the tree.")

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

		# Add multiple tags at once.
		self.backend.tag_job('child1_1', ['workspace:1', 'application:1'], self.stop)
		self.wait()
		self.backend.find_by_tag('application:1', self.stop)
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
		self.backend.set_attrs('child1_1', {'state': constants.JOB.SUCCESS}, self.stop)
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

		# Delete the tree.
		self.backend.delete_tree('child1', self.stop)
		self.wait()

		# Make sure we can't find it by tag anymore.
		self.backend.find_by_tag('workspace:1', self.stop)
		tagged_jobs = self.wait()

		self.assertEquals(len(tagged_jobs), 0, "Didn't delete the tags.")

		# Try to fetch the tree.
		for job_id in ['child1', 'child1_1', 'child2', 'root']:
			self.backend.get_tree(job_id, self.stop)
			tree = self.wait()

			self.assertEquals(len(tree), 0, "Didn't delete the tree.")

		# Try a different query.
		self.backend.get_ready_to_run('here', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 0 , "Should have returned no entries.")

	def test_tree_change(self):
		self.backend.add_job('here', 'root', None, self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'child1', 'root', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'child2', 'root', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'child1_1', 'child1', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'root2', None, self.stop, constants.JOB.WAITING)
		self.wait()

		# Look for ready to run jobs.
		self.backend.get_ready_to_run('here', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()
		self.assertEquals(len(jobs), 1, "Not the right number of ready jobs.")
		self.assertIn('root2', jobs, "Root2 wasn't ready to run.")

		# Update the whole tree.
		self.backend.set_state_tree('child1', constants.JOB.NEW, constants.JOB.WAITING, self.stop)
		self.wait()

		# Debug helper.
		#self.dump_job_tree('root', self.backend)
		#self.wait()

		# So now find waiting jobs.
		self.backend.get_ready_to_run('here', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()
		self.assertEquals(len(jobs), 3, "Not the right number of ready jobs.")
		self.assertIn('root2', jobs, "Root2 wasn't ready to run.")
		self.assertIn('child2', jobs, "Child2 wasn't ready to run.")
		self.assertIn('child1_1', jobs, "Child1_1 wasn't ready to run.")

	def test_tree_change_multinode(self):
		self.backend.add_job('here', 'root', None, self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'child1', 'root', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'child2', 'root', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('there', 'child1_1', 'child1', self.stop, constants.JOB.NEW)
		self.wait()
		self.backend.add_job('here', 'root2', None, self.stop, constants.JOB.NEW)
		self.wait()

		# Update only the nodes on 'there'.
		self.backend.set_state_tree('child1', constants.JOB.NEW, constants.JOB.WAITING, self.stop, node='there')
		self.wait()

		# Debug helper.
		#self.dump_job_tree('root', self.backend)
		#self.wait()

		# So now find waiting jobs.
		self.backend.get_ready_to_run('there', constants.JOB.WAITING, constants.JOB.SUCCESS, self.stop)
		jobs = self.wait()
		self.assertEquals(len(jobs), 1, "Not the right number of ready jobs.")
		self.assertIn('child1_1', jobs, "Child1_1 wasn't ready to run.")

		# Fetch the whole tree.
		self.backend.get_tree('child1', self.stop, node='here')
		tree = self.wait()
		self.assertEquals(len(tree), 3, "Failed to fetch the whole tree.")

		# Fetch the tree by state.
		self.backend.get_tree('child1', self.stop, state=constants.JOB.NEW, node='here')
		tree = self.wait()
		self.assertEquals(len(tree), 3, "Failed to fetch the tree.")

	def on_job_status_update(self, message):
		self.stop(message)

	def test_pubsub(self):
		# Subscribe so we can catch the status update as it comes out.
		nodeuuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(nodeuuid)

		job_id = str(uuid.uuid4())
		pub.subscribe(self.on_job_status_update, self.configuration.get_job_status_pub_topic(job_id))

		# Now send off a job update. This should exit via the pub/sub system, but be dropped
		# on the incoming side.
		self.configuration.send_job_status(job_id, state='TEST')
		status = self.wait()
		self.assertEquals(status.job_id, job_id, "Job ID was not as expected.")
		self.assertEquals(status.state, 'TEST', "Job status was not as expected.")

		# Now, manually send a status and force it to go via the pub/sub system and
		# back out again.
		job_id = str(uuid.uuid4())
		pub.subscribe(self.on_job_status_update, self.configuration.get_job_status_pub_topic(job_id))

		message = paasmaker.common.configuration.JobStatusMessage(job_id, 'ROUNDTRIP', 'BOGUS')
		message.unittest_override = True
		self.backend.send_job_status(message)

		status = self.wait()
		self.assertEquals(status.job_id, job_id, "Job ID was not as expected.")
		self.assertEquals(status.state, 'ROUNDTRIP', "Job status was not as expected.")
		self.assertEquals(status.source, 'BOGUS', 'Source was correct.')

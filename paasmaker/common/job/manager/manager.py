	#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import uuid
import json

import paasmaker
from paasmaker.common.core import constants
from backendredis import RedisJobBackend
from ...testhelpers import TestHelpers
from ..base import BaseJob

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
		self.in_startup = {}
		self.abort_handlers = {}
		self.double_process_filter = {}

		logger.debug("Subscribing to job status updates.")
		pub.subscribe(self.job_status, 'job.status')

	def prepare(self, callback, error_callback):
		"""
		Prepare the job manager, setting up the appropriate backend.
		Calls the supplied callbacks when ready.
		"""
		def abort_existing_jobs(message):
			my_uuid = self.configuration.get_node_uuid()
			def got_running_jobs(joblist):
				# Abort them.
				if len(joblist) == 0:
					# Nothing to do.
					callback(message)
				else:
					# Abort those jobs.
					def abort_one(aborted_message):
						try:
							job_id = joblist.pop()

							self.force_abort(job_id, my_uuid, abort_one)

						except KeyError, ex:
							# No more to pop off.
							callback(message)

						# end of abort_one()

					# Start aborting.
					abort_one('First job')

				# end of got_running_jobs()

			# On startup, mark any jobs that were RUNNING
			# as ABORTED. This handles jobs that did not finish
			# due to an error that caused Paasmaker to crash.
			# This frees up other nodes who might be depending on
			# the jobs.
			self.backend.get_node_jobs(
				my_uuid,
				got_running_jobs,
				state=constants.JOB.RUNNING
			)

			# end of abort_existing_jobs()

		self.backend.setup(abort_existing_jobs, error_callback)
		self.watchdog = JobManagerBackendWatchdog(self.configuration, self.backend)

	def set_context(self, job_id, context, callback):
		"""
		Set the initial context for a job. If called after the job has
		started, it will update the context, but you'll want to do this with
		caution.
		"""
		self.backend.store_context(job_id, context, callback)

	def get_context(self, job_id, callback):
		"""
		Get the context for a job. Intended for debugging and unit testing.
		"""
		self.backend.get_context(job_id, callback)

	def add_job(self, plugin, parameters, title, callback, parent=None, node=None, context=None, tags=[], abort_handler=False):
		"""
		Add the given job to the system, calling the callback with the
		assigned job id when it's inserted into the system. New jobs
		are inserted with the state NEW, which means they won't be executed
		until that tree is moved into the WAITING state.
		"""
		# Sanity check: make sure the given plugin exists
		# and can be called as a job. TODO: This only checks if the plugin
		# exists on the node that queued the job... which may or may not
		# have the plugin! To work around this for the moment, all nodes
		# have all the job plugins.
		if not self.configuration.plugins.exists(plugin, paasmaker.util.plugin.MODE.JOB):
			raise ValueError("Plugin %s doesn't exist in the JOB mode." % plugin)

		# Generate a job_id.
		job_id = str(uuid.uuid4())
		logger.info("Adding job '%s'", title)
		logger.debug("Allocated job id %s", job_id)

		# Figure out what node it belongs to. If supplied, use that one.
		# Otherwise it's considered a local job.
		if node:
			resolved_node = node
		else:
			resolved_node = self.configuration.get_node_uuid()

		def on_context_stored():
			# Send the NEW status around the cluster. In case something wants it.
			self.configuration.send_job_status(job_id, constants.JOB.NEW, parent_id=parent)
			# Ok, we added the job. Call the callback with the new job_id.
			logger.debug("Completed adding new job %s.", job_id)
			callback(job_id)

		def on_job_added():
			# Now, store the context for that job, if provided.
			# If not provided, proceed to the next stage.
			if context:
				logger.debug("Storing context for job %s: %s", job_id, str(context))
				self.backend.store_context(job_id, context, on_context_stored)
			else:
				on_context_stored()

		# Ask the backend to add the job.
		self.backend.add_job(
			resolved_node,
			job_id,
			parent,
			on_job_added,
			state=constants.JOB.NEW,
			plugin=plugin,
			parameters=parameters,
			title=title,
			tags=tags
		)

		# Make a note of this being an abort handler.
		if abort_handler:
			self.abort_handlers[job_id] = True

	def get_specifier(self):
		return JobSpecifier()

	def add_tree(self, treespec, callback, parent=None):
		self._add_tree_recurse(treespec, callback, parent)

	def _add_tree_recurse(self, tree, callback, parent=None):
		# Record a list of the children that we can destroy later.
		child_list = list(tree.children)
		child_list.reverse()

		def on_root_added(root_id):
			# Root has been added. Start popping off
			# children and adding them.
			tree.job_id = root_id

			def pop_child():
				try:
					child = child_list.pop()

					def child_done(child_id):
						child.job_id = child_id
						# Work on the next child.
						pop_child()
						# end of child_done()

					self._add_tree_recurse(child, child_done, parent=root_id)

				except IndexError, ex:
					# No more children. We're finished.
					callback(root_id)
				# end of pop_child()

			# Start processing children.
			pop_child()
			# End of on_root_added()

		# Add the root job.
		self.add_job(
			tree.parameters['plugin'],
			tree.parameters['parameters'],
			tree.parameters['title'],
			on_root_added,
			parent=parent,
			node=tree.parameters['node'],
			context=tree.parameters['context'],
			tags=tree.parameters['tags'],
			abort_handler=tree.parameters['abort_handler']
		)

	def allow_execution(self, job_id, callback=None, notify_others=True):
		"""
		Allow the entire job tree given by job_id (which can be anywhere on the tree)
		to commence execution. Optionally call the callback when done. This does not
		start evaluating jobs, but you can easily have it do that by setting
		the callback to the job managers evaluate function.
		"""
		def on_tree_updated(result):
			if notify_others:
				# Send a WAITING broadcast for the root job. This should trigger
				# other nodes to look at their jobs and start evaluating them.
				self.configuration.send_job_status(job_id, constants.JOB.WAITING)

			if callback:
				callback()

		self.backend.set_state_tree(job_id, constants.JOB.NEW, constants.JOB.WAITING, on_tree_updated)

	def allow_execution_list(self, job_ids, callback=None, notify_others=True):
		"""
		Allow several trees of jobs to be executable in one go.
		"""
		jobs_copy = list(job_ids)
		jobs_copy.reverse()

		def process_job():
			try:
				job_id = jobs_copy.pop()

				self.allow_execution(job_id, callback=process_job, notify_others=notify_others)
			except IndexError, ex:
				# No more entries.
				if callback:
					callback()

		process_job()

	def _start_job(self, job_id):
		# Prevent trying to start the same job twice (race conditions around
		# waiting for callbacks cause this - it can be kicked off twice until
		# the state is marked as running, so this stops that from happening.)
		# NOTE: This works also because only the node that is assigned the job
		# can act on or mutate the job.
		if self.in_startup.has_key(job_id):
			return
		self.in_startup[job_id] = True

		def on_context(context):
			def on_running(result):
				# Finally kick it off...
				logger.debug("Finally kicking off job %s", job_id)

				# Closure job to keep the job_id.
				# This function handles an exception when a job raises an exception.
				def handle_exception_job(exc_type, ex, traceback):
					# Log what happened.
					logging.error("Job %s failed with exception:", job_id, exc_info=True)
					job_logger = self.configuration.get_job_logger(job_id)
					job_logger.error("Job %s failed with exception:", job_id, exc_info=True)
					# Abort the job with an error.
					self.completed(job_id, constants.JOB.FAILED, None, "Exception thrown: " + str(ex))

					# Absorb the exception.
					return True

				with tornado.stack_context.ExceptionStackContext(handle_exception_job):
					self.runners[job_id].start_job(context)

			# Now that we have the context, we can start the job off.
			# Mark it as running and then get started.
			# TODO: There might be race conditions here...
			# But we've alieviated them above.
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
			plugin.configure(self, job_id, job)

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
			# Remove from abort handlers, if present (save the memory)
			# TODO: Figure out the right place to do this - this isn't it.
			#if self.abort_handlers.has_key(job_id):
			#	del self.abort_handlers[job_id]
			# Now publish the fact that the job has reached the given state.
			self.configuration.send_job_status(job_id, state, summary=summary)

		def on_job_metadata(metadata):
			# If the job was already in a finished state, DO NOT
			# update it's state and summary. Otherwise SUCCESS/ERROR jobs
			# turn into ABORTED jobs.
			if metadata['state'] not in constants.JOB_FINISHED_STATES:
				# Update the job state first.
				self.backend.set_attrs(
					job_id,
					{
						'state': state,
						'summary': summary
					},
					on_state_updated
				)
			else:
				on_state_updated(metadata)

		def on_context_updated():
			# Fetch the existing job metadata.
			self.backend.get_job(job_id, on_job_metadata)

		logger.debug("Job %s reports state %s.", job_id, state)

		if state in constants.JOB_FINISHED_STATES:
			# Close off the log file. There is a fair chance that it
			# won't be used again.
			paasmaker.util.joblogging.JobLoggerAdapter.finished_job(job_id)

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
			# Broadcast the fact that the job has been aborted.
			for job in jobs:
				self.configuration.send_job_status(job, constants.JOB.ABORTED, summary="Aborted due to a related job.")
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

		# ABORT HANDLER HANDLING
		def on_complete_tree(tree):
			def on_job_metadata(job):
				# Now that we have the job metadata, we can try to instantiate the plugin.
				job_id = job['job_id']
				logger.debug("ABORT HANDLER: Got metadata for job %s", job_id)
				job_logger = self.configuration.get_job_logger(job_id)
				plugin = self.configuration.plugins.instantiate(
					job['plugin'],
					paasmaker.util.plugin.MODE.JOB,
					job['parameters'],
					job_logger
				)
				plugin.configure(self, job_id, job)

				def on_context(context):
					# Just start the job immediately. If it throws an exception, we
					# don't cancel it or change anything else. At this stage, it's
					# cleaning up after another failure and as such we're not making
					# any guarantees about it.
					logger.debug("ABORT HANDLER: Got context for job %s", job_id)
					logger.debug("ABORT HANDLER: Context for job %s: %s", job_id, str(context))
					plugin.abort_handler(context)

				# Now we need to fetch the context to start the job off.
				self.backend.get_context(job_id, on_context)

			logger.info("Found %d jobs in the tree for abort handlers.", len(tree))
			for job in tree:
				if self.abort_handlers.has_key(job):
					# This is an abort handler.
					del self.abort_handlers[job]
					# Fetch the job metadata.
					self.backend.get_job(job, on_job_metadata)

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

		# Also, get the entire tree as well, to search for any abort handlers.
		logger.debug("Searching for entire tree to find abort handlers for %s.", message.job_id)
		self.backend.get_tree(
			message.job_id,
			on_complete_tree,
			node=self.configuration.get_node_uuid()
		)

	def job_status(self, message):
		# Extremely crude prevention for double processing messages.
		# TODO: Make this much nicer.
		# NOTE: This workaround is just a bandaid, and doesn't fix the
		# real issue that there are multiple paths in handling jobs
		# and related race conditions. However, for now, it will work.
		if len(self.double_process_filter) > 1000:
			# Reset it, to prevent it getting too large
			# and using too much memory.
			# TODO: Make this a LRU of some kind?
			self.double_process_filter = {}

		double_key = "%s:%s" % (message.job_id, message.state)
		if double_key in self.double_process_filter:
			# Already seen this key/state combination.
			return
		self.double_process_filter[double_key] = True

		if message.state in constants.JOB_SUCCESS_STATES or message.state == constants.JOB.WAITING:
			# If the message is a success state, or waiting, go
			# ahead and evaluate the jobs.
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

	def force_abort(self, job_id, node, callback):
		# Force abort this job. This is designed for Pacemakers to kill jobs
		# on down nodes. The default handling won't touch this because the
		# pacemaker node won't own the job.
		def on_waiting_altered(waiting_jobs):
			# Now broadcast the status.
			for job in waiting_jobs:
				self.configuration.send_job_status(job, constants.JOB.ABORTED, summary="Aborted due to a related job.")

			def on_running_altered(running_jobs):
				for job in running_jobs:
					self.configuration.send_job_status(job, constants.JOB.ABORTED, summary="Aborted due to a related job.")

				callback(waiting_jobs.union(running_jobs))

				# end of on_running_altered()

			# Do the same for RUNNING.
			logger.debug("Searching for WAITING jobs, and adjusting to aborted for tree %s.", job_id)
			self.backend.set_state_tree(
				job_id,
				constants.JOB.RUNNING,
				constants.JOB.ABORTED,
				on_running_altered,
				node=node
			)

			# end of on_waiting_altered()

		logger.debug("Force aborting jobs for node %s." % node)
		logger.debug("Searching for WAITING jobs, and adjusting to aborted for tree %s.", job_id)
		self.backend.set_state_tree(
			job_id,
			constants.JOB.WAITING,
			constants.JOB.ABORTED,
			on_waiting_altered,
			node=node
		)

	def debug_dump_job_tree(self, job_id, callback):
		def on_job_full(jobs):
			# Righto! Now we can sort and build this into a tree.
			results = []
			for job in jobs.values():
				simple_job_values = {
					'root_id': job['root_id'][0:8],
					'parent_id': (str(job['parent_id']))[0:8],
					'job_id': job['job_id'][0:8],
					'state': job['state'],
					'node': (str(job['node']))[0:8],
					'title': job['title']
				}
				results.append("R:%(root_id)s P:%(parent_id)s J:%(job_id)s => S:%(state)s N:%(node)s T:%(title)s" % simple_job_values)
			results.sort()
			for result in results:
				print result

			callback()

		def on_root_tree(tree):
			# Now fetch the complete job data on all these elements.
			self.backend.get_jobs(tree, on_job_full)

		def on_found_root(root_id):
			# Find the root's entire tree.
			self.backend.get_tree(root_id, on_root_tree)

		self.backend.get_root(job_id, on_found_root)

	def find_by_tag(self, tag, callback, limit=None):
		self.backend.find_by_tag(tag, callback, limit=limit)

	def find_older_than(self, age, callback, limit=None):
		self.backend.find_older_than(age, callback, limit=limit)

	def get_node_jobs(self, node, callback, state=None):
		self.backend.get_node_jobs(node, callback, state=state)

	def delete_tree(self, job_id, callback):
		self.backend.delete_tree(job_id, callback)

	def get_jobs(self, jobs, callback):
		self.backend.get_jobs(jobs, callback)

	def get_flat_tree(self, job_id, callback):
		self.backend.get_tree(job_id, callback)

	def get_pretty_tree(self, job_id, callback):
		# Step 1: Fetch all the IDs in this tree.
		# Step 2: Fetch full data on all those jobs.
		# Step 3: Sort it into nested dicts.
		def on_job_full(jobs):
			# Righto! Now we can sort and build this into a tree.
			roots = {}
			for job_id, job_data in jobs.iteritems():
				job_subset = {
					'root_id': job_data['root_id'],
					'parent_id': job_data['parent_id'],
					'job_id': job_data['job_id'],
					'state': job_data['state'],
					'node': job_data['node'],
					'title': job_data['title'],
					'time': job_data['time'],
					'summary': None
				}

				if job_data.has_key('summary'):
					job_subset['summary'] = job_data['summary']

				if not roots.has_key(job_id):
					roots[job_id] = {'children': []}
				roots[job_id].update(job_subset)

				parent_id = job_data['parent_id']
				if parent_id:
					if not roots.has_key(parent_id):
						roots[parent_id] = {'children': []}

					roots[parent_id]['children'].append(roots[job_id])

			if roots.has_key(on_job_full.root_id):
				callback(roots[on_job_full.root_id])
			else:
				# No such job.
				callback({})

		def on_root_tree(tree):
			# Now fetch the complete job data on all these elements.
			self.backend.get_jobs(tree, on_job_full)

		def on_found_root(root_id):
			# Find the root's entire tree.
			on_job_full.root_id = root_id
			self.backend.get_tree(root_id, on_root_tree)

		self.backend.get_root(job_id, on_found_root)

class JobManagerBackendWatchdog(object):
	"""
	A class to periodically check that the backend for the job
	manager is still running. It's up to the backend to take
	the appropriate action to make sure it's still operating.
	"""
	def __init__(self, configuration, backend):
		self.configuration = configuration
		self.backend = backend

		# Create the periodic handler.
		self.periodic = tornado.ioloop.PeriodicCallback(
			self.trigger,
			configuration.get_flat('job_manager_check_interval'),
			io_loop=configuration.io_loop
		)

		# Flag to store if the periodic has started.
		self.started = False

	def enable(self):
		if not self.started:
			self.periodic.start()
			self.started = True

	def disable(self):
		if self.started:
			self.periodic.stop()
			self.started = False

	def trigger(self):
		logger.debug("Job manager backend watchdog: performing check.")
		self.backend.ensure_connected()

class JobSpecifier(object):

	def __init__(self):
		self.children = []
		self.parameters = {}

	def set_job(self, plugin, parameters, title, node=None, context=None, tags=[], abort_handler=False):
		self.parameters['plugin'] = plugin
		self.parameters['parameters'] = parameters
		self.parameters['title'] = title
		self.parameters['node'] = node
		self.parameters['context'] = context
		self.parameters['tags'] = tags
		self.parameters['abort_handler'] = abort_handler

	def add_child(self):
		spec = JobSpecifier()
		self.children.append(spec)

		return spec

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

class TestFailJobRunnerNoAbortHandler(BaseJob):
	def start_job(self, context):
		self.failed("Failed to run.")

class TestAbortJobRunner(BaseJob):
	def start_job(self, context):
		# Do nothing - we're running now.
		pass

	def abort_job(self):
		self.aborted("Aborted.")

class TestExceptionCallbackJobRunner(BaseJob):
	def start_job(self, context):
		# Add a callback to throw an exception.
		# This thus occurs in a different context.
		self.configuration.io_loop.add_callback(self._throw_exception)

	def abort_job(self):
		self.aborted("Aborted.")

	def _throw_exception(self):
		raise Exception("Oh hai!")

class TestExceptionStartJobRunner(BaseJob):
	def start_job(self, context):
		raise Exception("Oh hai!")

	def abort_job(self):
		self.aborted("Aborted.")

class TestSyntaxErrorJobRunner(BaseJob):
	def start_job(self, context):
		os.foo("Bar")

class TestSyntaxErrorCallbackJobRunner(BaseJob):
	def start_job(self, context):
		self.configuration.io_loop.add_callback(self._syntax_error)

	def _syntax_error(self):
		os.foo("Bar")

ABORT_HANDLER_RESPONSE = None
class TestAbortHandlerJobRunner(BaseJob):
	def start_job(self, context):
		self.failed("Test failure")

	def abort_handler(self, context):
		global ABORT_HANDLER_RESPONSE
		ABORT_HANDLER_RESPONSE = "I'm in the abort handler."

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
			{},
			'Test Success Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.failure',
			'paasmaker.common.job.manager.manager.TestFailJobRunner',
			{},
			'Test Fail Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.failure.noabort',
			'paasmaker.common.job.manager.manager.TestFailJobRunnerNoAbortHandler',
			{},
			'Test Fail Job with no Abort Handler'
		)
		self.configuration.plugins.register(
			'paasmaker.job.aborted',
			'paasmaker.common.job.manager.manager.TestAbortJobRunner',
			{},
			'Test Abort Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.exceptioncallback',
			'paasmaker.common.job.manager.manager.TestExceptionCallbackJobRunner',
			{},
			'Test Exception Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.exceptionstart',
			'paasmaker.common.job.manager.manager.TestExceptionStartJobRunner',
			{},
			'Test Exception Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.syntaxerrorstart',
			'paasmaker.common.job.manager.manager.TestSyntaxErrorJobRunner',
			{},
			'Test Syntax Error'
		)
		self.configuration.plugins.register(
			'paasmaker.job.syntaxerrorcallbackstart',
			'paasmaker.common.job.manager.manager.TestSyntaxErrorCallbackJobRunner',
			{},
			'Test Syntax Error Callback'
		)
		self.configuration.plugins.register(
			'paasmaker.job.aborthandler',
			'paasmaker.common.job.manager.manager.TestAbortHandlerJobRunner',
			{},
			'Test Abort Handler Job'
		)

		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
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

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.SUCCESS, 'Test job was not successful.')

	def test_manager_success_simple_multiexecute(self):
		# Set up a simple successful job.
		self.manager.add_job('paasmaker.job.success', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution_list([job_id], callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.SUCCESS, 'Test job was not successful.')

	def test_manager_failed_job_simple(self):
		# Set up a simple failed job.
		self.manager.add_job('paasmaker.job.failure', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job was not a failure.')

	def test_manager_failed_job_no_abort_handler(self):
		# Set up a simple failed job.
		self.manager.add_job('paasmaker.job.failure.noabort', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job was not a failure.')

	def test_manager_success_tree(self):
		# Test that a subtree processes correctly.
		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id, tags=['test'])
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		#self.dump_job_tree(root_id, self.manager.backend)
		#self.wait()

		# Wait for it to settle down; TODO: this should actually detect when the job is finished
		self.short_wait_hack(length=0.5)

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.SUCCESS, "Sub 2 should have succeeded.")
		self.assertEquals(root_status, constants.JOB.SUCCESS, "Root should have succeeded.")

		# Fetch out the jobs by tag.
		self.manager.find_by_tag('test', self.stop)
		result = self.wait()

		self.assertEquals(len(result), 1, "Returned incorrect number of tagged jobs.")
		self.assertEquals(result[0], root_id, "Wrong tagged job returned.")

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
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		self.short_wait_hack(length=0.2)

		self.manager.get_pretty_tree(root_id, self.stop)
		tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		subsub1_status = self.get_state(subsub1_id)
		sub1_status = self.get_state(sub1_id)
		sub2_status = self.get_state(sub2_id)
		root_status = self.get_state(root_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.ABORTED, "Sub 1 should have been aborted.")
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
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		#self.dump_job_tree(root_id, self.manager.backend)
		#self.wait()

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

		# And, to fix a bug - the jobs that were aborted should have broadcast that status.
		self.assertEquals(self.statuses[sub2_id].state, constants.JOB.ABORTED)
		self.assertEquals(self.statuses[root_id].state, constants.JOB.ABORTED)

	def test_manager_exception_callback(self):
		# Set up a simple exception job.
		self.manager.add_job('paasmaker.job.exceptioncallback', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job did not fail.')

	def test_manager_exception_start(self):
		# Set up a simple exception job.
		self.manager.add_job('paasmaker.job.exceptionstart', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job did not fail.')

		job_path = self.configuration.get_job_log_path(job_id)

	def test_manager_syntax_error_start(self):
		# Set up a simple exception job.
		self.manager.add_job('paasmaker.job.syntaxerrorstart', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job did not fail.')

	def test_manager_syntax_error_callback_start(self):
		# Set up a simple exception job.
		self.manager.add_job('paasmaker.job.syntaxerrorcallbackstart', {}, "Example job.", self.stop)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack()

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job did not fail.')

	def test_manager_abort_handler(self):
		# Set up a simple abort handler job.
		self.manager.add_job('paasmaker.job.aborthandler', {}, "Example job.", self.stop, abort_handler=True)
		job_id = self.wait()

		self.manager.allow_execution(job_id, callback=self.stop)
		self.wait()

		self.short_wait_hack(length=0.3)

		#self.dump_job_tree(job_id, self.manager.backend)
		#self.wait()

		result = self.get_state(job_id)
		self.assertEquals(result, constants.JOB.FAILED, 'Test job did not fail.')
		self.assertNotEquals(ABORT_HANDLER_RESPONSE, None, 'Abort handler did not run.')

	def test_manager_no_job(self):
		self.manager.get_jobs(['nope'], self.stop)
		job_data = self.wait()

		self.assertEquals(len(job_data), 0, "Returned some job data.")

		self.manager.get_flat_tree('nope', self.stop)
		tree = self.wait()

		self.manager.get_pretty_tree('nope', self.stop)
		tree = self.wait()

	def test_manager_proceedural_tree(self):
		# Test out the easier to use proceedural tree API.

		root = JobSpecifier()
		root.set_job('paasmaker.job.success', {}, "Example root job.")

		sub1 = root.add_child()
		sub1.set_job('paasmaker.job.success', {}, "Example sub1 job.", tags=['test'])

		sub1_1 = sub1.add_child()
		sub1_1.set_job('paasmaker.job.success', {}, "Example subsub1 job.")

		sub2 = root.add_child()
		sub2.set_job('paasmaker.job.success', {}, "Example sub2 job.")

		self.manager.add_tree(root, self.stop)
		root_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		#self.dump_job_tree(root_id)
		#self.wait()

		# Wait for it to settle down.
		self.short_wait_hack(length=0.2)

		subsub1_status = self.get_state(sub1_1.job_id)
		sub1_status = self.get_state(sub1.job_id)
		sub2_status = self.get_state(sub2.job_id)
		root_status = self.get_state(root.job_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.SUCCESS, "Sub 2 should have succeeded.")
		self.assertEquals(root_status, constants.JOB.SUCCESS, "Root should have succeeded.")

		# Fetch out the jobs by tag.
		self.manager.find_by_tag('test', self.stop)
		result = self.wait()

		self.assertEquals(len(result), 1, "Returned incorrect number of tagged jobs.")
		self.assertEquals(result[0], root_id, "Wrong tagged job returned.")

	def test_manager_proceedural_tree_graft(self):
		# Test out the easier to use proceedural tree API.

		root = JobSpecifier()
		root.set_job('paasmaker.job.success', {}, "Example root job.")

		sub1 = root.add_child()
		sub1.set_job('paasmaker.job.success', {}, "Example sub1 job.", tags=['test'])

		sub2 = root.add_child()
		sub2.set_job('paasmaker.job.success', {}, "Example sub2 job.")

		self.manager.add_tree(root, self.stop)
		root_id = self.wait()

		# Graft on another tree.
		sub1_1 = JobSpecifier()
		sub1_1.set_job('paasmaker.job.success', {}, "Example subsub1 job.")

		self.manager.add_tree(sub1_1, self.stop, parent=sub1.job_id)
		self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		#self.dump_job_tree(root_id)
		#self.wait()

		# Wait for it to settle down.
		self.short_wait_hack(length=0.2)

		#self.manager.get_pretty_tree(root_id, self.stop)
		#tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		# TODO: Verify programatically that sub1_1's parent is sub1.
		# I've checked this in the debug output, but it's better if the unit test does this.

		subsub1_status = self.get_state(sub1_1.job_id)
		sub1_status = self.get_state(sub1.job_id)
		sub2_status = self.get_state(sub2.job_id)
		root_status = self.get_state(root.job_id)

		self.assertEquals(subsub1_status, constants.JOB.SUCCESS, "Sub Sub 1 should have succeeded.")
		self.assertEquals(sub1_status, constants.JOB.SUCCESS, "Sub 1 should have succeeded.")
		self.assertEquals(sub2_status, constants.JOB.SUCCESS, "Sub 2 should have succeeded.")
		self.assertEquals(root_status, constants.JOB.SUCCESS, "Root should have succeeded.")

		# Fetch out the jobs by tag.
		self.manager.find_by_tag('test', self.stop)
		result = self.wait()

		self.assertEquals(len(result), 1, "Returned incorrect number of tagged jobs.")
		self.assertEquals(result[0], root_id, "Wrong tagged job returned.")

	def test_manager_startup_abort_jobs(self):
		root = JobSpecifier()
		root.set_job('paasmaker.job.success', {}, "Example root job.")

		sub1 = root.add_child()
		sub1.set_job('paasmaker.job.success', {}, "Example sub1 job.", tags=['test'])

		sub1_1 = sub1.add_child()
		sub1_1.set_job('paasmaker.job.success', {}, "Example subsub1 job.")

		sub2 = root.add_child()
		sub2.set_job('paasmaker.job.success', {}, "Example sub2 job.")

		self.manager.add_tree(root, self.stop)
		root_id = self.wait()

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		# TODO: This test is time sensitive. This is obviously not a good
		# thing to be.
		self.short_wait_hack(length=0.05)

		# Immediately prepare the system again. This should
		# query and cancel running jobs.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

		#self.dump_job_tree(root_id)
		#self.wait()

		# Wait for it to settle down.
		self.short_wait_hack(length=0.2)

		subsub1_status = self.get_state(sub1_1.job_id)
		sub1_status = self.get_state(sub1.job_id)
		sub2_status = self.get_state(sub2.job_id)
		root_status = self.get_state(root.job_id)

		# TODO: This is rather unscientific and based on the time it takes.
		# At least one of the jobs should have been aborted.
		aborted_count = 0
		if subsub1_status == constants.JOB.ABORTED: aborted_count += 1
		if sub1_status == constants.JOB.ABORTED: aborted_count += 1
		if sub2_status == constants.JOB.ABORTED: aborted_count += 1
		if root_status == constants.JOB.ABORTED: aborted_count += 1

		self.assertTrue(aborted_count > 0, "None of the jobs got aborted. See notes in the unit test.")
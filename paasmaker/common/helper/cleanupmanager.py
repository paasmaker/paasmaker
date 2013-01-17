
import json
import datetime

import paasmaker
from paasmaker.common.core import constants
from paasmaker.util.plugin import MODE
from ..cleaner.base import BaseCleaner
from ..job.base import BaseJob
from ..testhelpers import TestHelpers

import tornado
import tornado.testing
import colander
from pubsub import pub

class CleanupManager(object):
	"""
	A class to manage the cleanup plugins.

	This manager runs the defined cleanup plugins with the period given.
	These are designed to prune old files, remove old jobs, or other such
	cleanup tasks to keep the local filesystems free of cruft. In a perfect
	world, each part of the system would clean up after itself, but in
	the real world, errors occur that prevent some cleanup from happening.
	"""
	def __init__(self, configuration):
		self.configuration = configuration
		self._cleaners = {}

		for cleanup in self.configuration['cleaners']:
			plugin = cleanup['plugin']
			self._cleaners[plugin] = {
				'running': False,
				'periodic': self._make_periodic_trigger(plugin, cleanup['interval'])
			}

	def _make_periodic_trigger(self, name, interval):
		# Anonymous trigger function, to encapsulate the
		# plugin name in a closure.
		def trigger():
			self.trigger(name)

		return tornado.ioloop.PeriodicCallback(
			trigger,
			interval * 1000,
			io_loop=self.configuration.io_loop
		)

	def start(self):
		"""
		Enable running cleanup tasks according to their interval.
		"""
		for cleaner in self._cleaners.values():
			cleaner['periodic'].start()

	def suspend(self):
		"""
		Suspend running all cleaners. Cleaners in progress can finish.
		"""
		for cleaner in self._cleaners.values():
			cleaner['periodic'].stop()

	def is_running(self, cleaner):
		"""
		Determine if the given cleaner is currently running.

		:arg str cleaner: The cleaner to check.
		"""
		if not self._cleaners.has_key(cleaner):
			raise NameError("No such cleaner %s." % cleaner)

		return self._cleaners[cleaner]['running']

	def trigger(self, cleaner, callback=None):
		"""
		Trigger off a cleaner. Optionally call the callback
		once it's done.

		:arg str cleaner: The cleaner to run now.
		:arg callable callback: The optional callback to call once
			the jobs are submitted. (Note: not when they are complete.)
		"""
		if not self._cleaners.has_key(cleaner):
			raise NameError("No such cleaner %s." % group)

		if self.is_running(cleaner):
			if callback:
				callback(None)
			return

		metadata = self._cleaners[cleaner]

		# Submit all the appropriate jobs.
		# When jobs are done, it should mark that cleaner as finished.
		tree = self.configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.cleaner',
			{
				'plugin': cleaner
			},
			"Cleaner task %s, node %s, at %s" % (cleaner, self.configuration.get_node_uuid()[0:8], datetime.datetime.utcnow().isoformat()),
			tags=['cleaner', 'cleaner_task:%s' % cleaner, 'cleaner_node:%s' % self.configuration.get_node_uuid()],
			abort_handler=True
		)

		# Now submit the jobs.
		def on_tree_added(root_id):
			def on_executable():
				if callback:
					callback(root_id)
				else:
					# Well, that's it.
					return

			self.configuration.job_manager.allow_execution(root_id, on_executable)

		self._cleaners[cleaner]['running'] = True
		self.configuration.job_manager.add_tree(tree, on_tree_added)

	def mark_finished(self, cleaner):
		"""
		Mark the given cleaner as finished, so it can execute again.

		This is designed for the cleaner job to indicate that it's done,
		and is not designed for general use.
		"""
		if not self._cleaners.has_key(cleaner):
			raise NameError("No such cleaner %s." % cleaner)
		if self._cleaners[cleaner]['running']:
			self._cleaners[cleaner]['running'] = False

class CleanerRunJobParametersSchema(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String())

class CleanerRunJob(BaseJob):
	MODES = {
		MODE.JOB: CleanerRunJobParametersSchema()
	}

	def start_job(self, context):
		# This job will start the cleaner and manage the result of that.
		exists = self.configuration.plugins.exists(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.CLEANER
		)

		if not exists:
			error_message = "No such plugin %s" % self.parameters['plugin']
			self.logger.error(error_message)
			self.failed(error_message)
			return

		cleaner = self.configuration.plugins.instantiate(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.CLEANER,
			{},
			self.logger
		)

		def success(message):
			self.configuration.cleanup_manager.mark_finished(self.parameters['plugin'])
			self.success({}, message)

		def failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			self.failed(message)

		# Kick off the plugin.
		cleaner.clean(success, failure)

	def abort_job(self):
		self.aborted("Aborted due to request.")

	def abort_handler(self, context):
		# Mark it as finished, otherwise it might hang.
		self.configuration.cleanup_manager.mark_finished(self.parameters['plugin'])

##
## TESTING CODE
##

class CleanerTestPlugin(BaseCleaner):
	def clean(self, callback, error_callback):
		callback("Successfully cleaned up.")

class CleanerTestFailPlugin(BaseCleaner):
	def clean(self, callback, error_callback):
		error_callback("Generated an error.")

class CleanupManagerTest(tornado.testing.AsyncTestCase, TestHelpers):

	def setUp(self):
		super(CleanupManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid('test')
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

		# Inject test cleanup manager plugins.
		self.configuration.plugins.register(
			'paasmaker.cleaner.test',
			'paasmaker.common.helper.cleanupmanager.CleanerTestPlugin',
			{},
			'Test Cleaner plugin'
		)
		self.configuration.plugins.register(
			'paasmaker.cleaner.testfail',
			'paasmaker.common.helper.cleanupmanager.CleanerTestFailPlugin',
			{},
			'Test Fail Cleaner plugin'
		)

		# Set up to catch job statuses.
		pub.subscribe(self.on_job_catchall, 'job.status')
		self.job_statuses = {}

	def on_job_catchall(self, message):
		#print str(message.flatten())
		self.job_statuses[message.job_id] = message

	def tearDown(self):
		self.configuration.cleanup()
		super(CleanupManagerTest, self).tearDown()

	def _wait_until_state(self, job_id, state):
		finished = False
		maximum_loops = 25 # ~2.5 seconds
		while not finished:
			if self.job_statuses.has_key(job_id):
				finished = self.job_statuses[job_id].state == state

			maximum_loops -= 1
			if maximum_loops <= 0:
				break

			self.short_wait_hack()

	def test_simple(self):
		# Inject a test health manager configuration.
		cleaners = [
			{
				'plugin': 'paasmaker.cleaner.test',
				'interval': 3600
			},
			{
				'plugin': 'paasmaker.cleaner.testfail',
				'interval': 3600
			}
		]

		self.configuration['cleaners'] = cleaners

		self.configuration.startup_cleanup_manager(start_checking=False)
		manager = self.configuration.cleanup_manager

		# Trigger off the first plugin.
		manager.trigger('paasmaker.cleaner.test', self.stop)
		job_id = self.wait()

		self.assertTrue(manager.is_running('paasmaker.cleaner.test'), 'Not running cleaner.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.SUCCESS)
		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.SUCCESS, "Cleaner did not succeed.")
		self.assertFalse(manager.is_running('paasmaker.cleaner.test'), "Still running cleaner.")

		# Trigger off the fail plugin.
		manager.trigger('paasmaker.cleaner.testfail', self.stop)
		job_id = self.wait()

		#self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		#tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		self.assertTrue(manager.is_running('paasmaker.cleaner.testfail'), 'Not running cleaner.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.FAILED)

		self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		tree = self.wait()

		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.FAILED, "Cleaner did not fail.")
		self.assertFalse(manager.is_running('paasmaker.cleaner.testfail'), "Still running cleaner.")
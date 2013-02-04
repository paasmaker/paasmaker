
import json
import datetime

import paasmaker
from paasmaker.common.core import constants
from paasmaker.util.plugin import MODE
from ..periodic.base import BasePeriodic
from ..job.base import BaseJob
from ..testhelpers import TestHelpers

import tornado
import tornado.testing
import colander
from pubsub import pub

class PeriodicManager(object):
	"""
	A class to manage periodic plugins.

	This manager runs the defined periodic plugins with the period given.
	These are designed to prune old files, remove old jobs, or other such
	periodic tasks to keep the local filesystems free of cruft.
	"""
	def __init__(self, configuration):
		self.configuration = configuration
		self._periodics = {}

		for periodic in self.configuration['periodics']:
			plugin = periodic['plugin']
			self._periodics[plugin] = {
				'running': False,
				'periodic': self._make_periodic_trigger(plugin, periodic['interval'])
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
		Enable running periodic tasks according to their interval.
		"""
		for periodic in self._periodics.values():
			periodic['periodic'].start()

	def suspend(self):
		"""
		Suspend running all periodics. Periodics in progress can finish.
		"""
		for periodic in self._periodics.values():
			periodic['periodic'].stop()

	def is_running(self, periodic):
		"""
		Determine if the given periodic is currently running.

		:arg str periodic: The periodic to check.
		"""
		if not self._periodics.has_key(periodic):
			raise NameError("No such periodic %s." % periodic)

		return self._periodics[periodic]['running']

	def trigger(self, periodic, callback=None):
		"""
		Trigger off a periodic. Optionally call the callback
		once it's done.

		:arg str periodic: The periodic to run now.
		:arg callable callback: The optional callback to call once
			the jobs are submitted. (Note: not when they are complete.)
		"""
		if not self._periodics.has_key(periodic):
			raise NameError("No such periodic %s." % periodic)

		if self.is_running(periodic):
			if callback:
				callback(None)
			return

		metadata = self._periodics[periodic]

		# Submit all the appropriate jobs.
		# When jobs are done, it should mark that periodic as finished.
		tree = self.configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.periodic',
			{
				'plugin': periodic
			},
			"Periodic task %s, node %s, at %s" % (periodic, self.configuration.get_node_uuid()[0:8], datetime.datetime.utcnow().isoformat()),
			tags=['periodic', 'periodic_task:%s' % periodic, 'periodic_node:%s' % self.configuration.get_node_uuid()],
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

		self._periodics[periodic]['running'] = True
		self.configuration.job_manager.add_tree(tree, on_tree_added)

	def mark_finished(self, periodic):
		"""
		Mark the given periodic as finished, so it can execute again.

		This is designed for the periodic job to indicate that it's done,
		and is not designed for general use.
		"""
		if not self._periodics.has_key(periodic):
			raise NameError("No such periodic %s." % periodic)
		if self._periodics[periodic]['running']:
			self._periodics[periodic]['running'] = False

class PeriodicRunJobParametersSchema(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String())

class PeriodicRunJob(BaseJob):
	MODES = {
		MODE.JOB: PeriodicRunJobParametersSchema()
	}

	def start_job(self, context):
		# This job will start the periodic and manage the result of that.
		exists = self.configuration.plugins.exists(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.PERIODIC
		)

		if not exists:
			error_message = "No such plugin %s" % self.parameters['plugin']
			self.logger.error(error_message)
			self.failed(error_message)
			return

		periodic = self.configuration.plugins.instantiate(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.PERIODIC,
			{},
			self.logger
		)

		def success(message):
			self.configuration.periodic_manager.mark_finished(self.parameters['plugin'])
			self.success({}, message)

		def failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			self.failed(message)

		# Kick off the plugin.
		periodic.on_interval(success, failure)

	def abort_job(self):
		self.aborted("Aborted due to request.")

	def abort_handler(self, context):
		# Mark it as finished, otherwise it might hang.
		self.configuration.periodic_manager.mark_finished(self.parameters['plugin'])

##
## TESTING CODE
##

class PeriodicTestPlugin(BasePeriodic):
	def on_interval(self, callback, error_callback):
		callback("Successfully cleaned up.")

class PeriodicTestFailPlugin(BasePeriodic):
	def on_interval(self, callback, error_callback):
		error_callback("Generated an error.")

class PeriodicManagerTest(tornado.testing.AsyncTestCase, TestHelpers):

	def setUp(self):
		super(PeriodicManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid('test')
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

		# Inject test periodic manager plugins.
		self.configuration.plugins.register(
			'paasmaker.periodic.test',
			'paasmaker.common.helper.periodicmanager.PeriodicTestPlugin',
			{},
			'Test Periodic plugin'
		)
		self.configuration.plugins.register(
			'paasmaker.periodic.testfail',
			'paasmaker.common.helper.periodicmanager.PeriodicTestFailPlugin',
			{},
			'Test Fail Periodic plugin'
		)

		# Set up to catch job statuses.
		pub.subscribe(self.on_job_catchall, 'job.status')
		self.job_statuses = {}

	def on_job_catchall(self, message):
		#print str(message.flatten())
		self.job_statuses[message.job_id] = message

	def tearDown(self):
		self.configuration.cleanup()
		super(PeriodicManagerTest, self).tearDown()

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
		periodics = [
			{
				'plugin': 'paasmaker.periodic.test',
				'interval': 3600
			},
			{
				'plugin': 'paasmaker.periodic.testfail',
				'interval': 3600
			}
		]

		self.configuration['periodics'] = periodics

		self.configuration.startup_periodic_manager(start_checking=False)
		manager = self.configuration.periodic_manager

		# Trigger off the first plugin.
		manager.trigger('paasmaker.periodic.test', self.stop)
		job_id = self.wait()

		self.assertTrue(manager.is_running('paasmaker.periodic.test'), 'Not running periodic.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.SUCCESS)
		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.SUCCESS, "Periodic did not succeed.")
		self.assertFalse(manager.is_running('paasmaker.periodic.test'), "Still running periodic.")

		# Trigger off the fail plugin.
		manager.trigger('paasmaker.periodic.testfail', self.stop)
		job_id = self.wait()

		#self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		#tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		self.assertTrue(manager.is_running('paasmaker.periodic.testfail'), 'Not running periodic.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.FAILED)

		self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		tree = self.wait()

		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.FAILED, "Periodic did not fail.")
		self.assertFalse(manager.is_running('paasmaker.periodic.testfail'), "Still running periodic.")
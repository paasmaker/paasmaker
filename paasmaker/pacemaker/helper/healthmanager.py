
import json
import datetime

import paasmaker
from paasmaker.common.core import constants
from paasmaker.util.plugin import MODE
from ..health.base import BaseHealthCheck

import tornado
import tornado.testing
import colander
from pubsub import pub

class HealthManager(object):
	"""
	A class to manage the health check plugins.

	The actions this manager takes it based on the configuration.
	The configuration has named groups of health checks (and should
	always have a 'default' group), which consist of a list of plugins
	and the order to run those checks in. Plugins with the same order
	will run concurrently, and lower order numbers run first.

	The health checks work by adding jobs which then call the health
	check plugins. This gives you the ability to audit the result of these
	health checks. The check plugins might submit more jobs to the tree
	to take corrective actions.

	Whilst they are called "health check" plugins, designed to find
	errors and fix them, there is no reason why plugins can't detect
	conditions that require scaling and make appropriate changes to
	handle these conditions.
	"""
	def __init__(self, configuration):
		# Set up the health groups.
		self.configuration = configuration
		self._groups = {}

		for group in configuration['pacemaker']['health']['groups']:
			name = group['name']
			if not self._groups.has_key(name):
				self._groups[name] = dict(group)
				self._groups[name]['running'] = False
				self._groups[name]['plugins'] = list(self._groups[name]['plugins'])

				# Sort the plugins into their order groups.
				by_order = {}
				orders = set()
				for plugin in self._groups[name]['plugins']:
					order_key = str(plugin['order'])
					if not by_order.has_key(order_key):
						by_order[order_key] = []
					by_order[order_key].append(plugin)
					orders.add(plugin['order'])

				self._groups[name]['by_order'] = by_order
				orders = list(orders)
				orders.sort()
				orders.reverse()
				self._groups[name]['orders'] = orders

		# For each group, create a periodic that can run it.
		# Don't start that periodic just yet.
		for group in self._groups.values():
			group['periodic'] = self._make_periodic_trigger(group['name'], group['period'])

	def _make_periodic_trigger(self, name, interval):
		# Anonymous trigger function, to encapsulate the
		# group name in a closure.
		def trigger():
			self.trigger(name)

		return tornado.ioloop.PeriodicCallback(
			trigger,
			interval * 1000,
			io_loop=self.configuration.io_loop
		)

	def start(self):
		"""
		Enable running health checks according to their configured schedules.
		"""
		for group in self._groups.values():
			group['periodic'].start()

	def suspend(self):
		"""
		Suspend running all health checks. Health checks in process
		are allowed to finish.
		"""
		for group in self._groups.values():
			group['periodic'].stop()

	def is_running(self, group):
		"""
		Determine if the given health check group is currently running.

		:arg str group: The group to check.
		"""
		if not self._groups.has_key(group):
			raise NameError("No such health check group %s." % group)

		return self._groups[group]['running']

	def trigger(self, group, callback=None):
		"""
		Trigger off a health check of the named group now. It will
		call the callback with the root job ID of the submitted jobs.
		If you don't care, you don't need to supply the callback.

		This will queue up jobs to run that particular health
		check, and start executing them. If an existing run of this
		health check is running, it will call the callback with
		the value None to indicate that it took no action.

		:arg str group: The group to check now.
		:arg callable callback: The optional callback to call once
			the jobs are submitted.
		"""
		if not self._groups.has_key(group):
			raise NameError("No such health check group %s." % group)

		if self.is_running(group):
			if callback:
				callback(None)
			return

		metadata = self._groups[group]

		context = {}
		context['group'] = group

		# Submit all the appropriate jobs.
		# When jobs are done, it should mark that group as finished.
		tree = self.configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.health.root',
			{
				'group': group
			},
			"Health checks for group %s, at %s" % (group, datetime.datetime.utcnow().isoformat()),
			context=context,
			tags=['health', 'health:%s' % group],
			abort_handler=True
		)

		container = tree

		# Go through the plugins, and add jobs at each level for each group.
		for order in metadata['orders']:
			order_key = str(order)

			plugins = metadata['by_order'][order_key]

			container = container.add_child()
			container.set_job(
				'paasmaker.job.container',
				{},
				"Checks in order %d" % order
			)

			# To that container, add the plugins.
			for plugin in plugins:
				task = container.add_child()
				task.set_job(
					'paasmaker.job.health.check',
					plugin,
					"Health check %s" % plugin['plugin']
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

		self._groups[group]['running'] = True
		self.configuration.job_manager.add_tree(tree, on_tree_added)

	def mark_finished(self, group):
		"""
		Mark the given group as finished, so it can execute again.

		This is designed for the health root job to indicate that it's done,
		and is not designed for general use.
		"""
		if not self._groups.has_key(group):
			raise NameError("No such health check group %s." % group)
		if self._groups[group]['running']:
			self._groups[group]['running'] = False

class HealthCheckRunJobParametersSchema(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String())
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		missing={},
		default={})

class HealthCheckRunJob(paasmaker.common.job.base.BaseJob):
	MODES = {
		MODE.JOB: HealthCheckRunJobParametersSchema()
	}

	def start_job(self, context):
		# This job will start the health check plugin and manage
		# the result of that.
		exists = self.configuration.plugins.exists(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.HEALTH_CHECK
		)

		if not exists:
			self.failed("No such plugin %s" % self.parameters['plugin'])
			return

		health = self.configuration.plugins.instantiate(
			self.parameters['plugin'],
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			self.parameters['parameters'],
			self.logger
		)

		def success(output_context, message):
			self.success(output_context, message)

		def failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			self.failed(message)

		# Kick off the plugin.
		health.check(self.job_metadata['root_id'], success, failure)

	def abort_job(self):
		self.aborted("Aborted due to request.")

class HealthCheckMarkCompletedJobParametersSchema(colander.MappingSchema):
	group = colander.SchemaNode(colander.String())

class HealthCheckMarkCompletedJob(paasmaker.common.job.base.BaseJob):
	MODES = {
		MODE.JOB: HealthCheckMarkCompletedJobParametersSchema()
	}

	def start_job(self, context):
		self.configuration.health_manager.mark_finished(self.parameters['group'])
		self.success({}, "Completed successfully.")

	def abort_handler(self, context):
		# Mark it as finished, otherwise it might hang.
		self.configuration.health_manager.mark_finished(self.parameters['group'])

	def abort_job(self):
		self.aborted("Aborted due to request.")

##
## TESTING CODE
##

class HealthCheckTestPlugin(BaseHealthCheck):
	def check(self, parent_job_id, callback, error_callback):
		callback({}, "Successfully checked health.")

class HealthCheckTestFailPlugin(BaseHealthCheck):
	def check(self, parent_job_id, callback, error_callback):
		error_callback("Generated an error.")

class HealthMangerTest(tornado.testing.AsyncTestCase, paasmaker.common.testhelpers.TestHelpers):

	def setUp(self):
		super(HealthMangerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

		# Inject test health manager plugins.
		self.configuration.plugins.register(
			'paasmaker.health.test',
			'paasmaker.pacemaker.helper.healthmanager.HealthCheckTestPlugin',
			{},
			'Test Health Check plugin'
		)
		self.configuration.plugins.register(
			'paasmaker.health.testfail',
			'paasmaker.pacemaker.helper.healthmanager.HealthCheckTestFailPlugin',
			{},
			'Test Fail Health Check plugin'
		)

		# Set up to catch job statuses.
		pub.subscribe(self.on_job_catchall, 'job.status')
		self.job_statuses = {}

	def on_job_catchall(self, message):
		#print str(message.flatten())
		self.job_statuses[message.job_id] = message

	def tearDown(self):
		self.configuration.cleanup()
		super(HealthMangerTest, self).tearDown()

	def _set_health_config(self, plugins):
		health = {
			'enabled': True,
			'groups': [
				{
					'name': 'default',
					'title': 'Default Health Check',
					'period': 60,
					'plugins': plugins
				}
			]
		}

		self.configuration['pacemaker']['health'] = health

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
		self._set_health_config(
			[
				{
					'plugin': 'paasmaker.health.test',
					'order': 10,
					'parameters': {}
				}
			]
		)

		self.configuration.startup_health_manager(start_checking=False)
		manager = self.configuration.health_manager

		# Trigger off the default check.
		manager.trigger('default', self.stop)
		job_id = self.wait()

		self.assertTrue(manager.is_running('default'), 'Not running default group.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.SUCCESS)
		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.SUCCESS, "Health check did not succeed.")
		self.assertFalse(manager.is_running('default'), "Still running default group.")

		# Test a failed batch.
		self._set_health_config(
			[
				{
					'plugin': 'paasmaker.health.testfail',
					'order': 10,
					'parameters': {}
				}
			]
		)

		self.configuration.startup_health_manager(start_checking=False)
		manager = self.configuration.health_manager

		# Trigger off the default check.
		manager.trigger('default', self.stop)
		job_id = self.wait()

		#self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		#tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		self.assertTrue(manager.is_running('default'), 'Not running default group.')

		# Give it a short while to finish.
		self.short_wait_hack()

		# Now loop until it's finished.
		self._wait_until_state(job_id, constants.JOB.ABORTED)

		self.configuration.job_manager.get_pretty_tree(job_id, self.stop)
		tree = self.wait()

		self.assertEquals(self.job_statuses[job_id].state, constants.JOB.ABORTED, "Health check did not abort.")
		self.assertFalse(manager.is_running('default'), "Still running default group.")
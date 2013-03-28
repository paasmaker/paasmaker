
import os

import paasmaker
from ..base import BaseJob
from paasmaker.util.plugin import MODE
from paasmaker.common.application.environment import ApplicationEnvironment

import colander

class PreInstanceStartupJobParametersSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.String())

class PreInstanceStartupJob(BaseJob):
	"""
	A job to run pre-startup commands. These are plugins defined
	in the application that should run just prior to starting up an instance.
	"""
	MODES = {
		MODE.JOB: PreInstanceStartupJobParametersSchema()
	}

	def done(self, message):
		self.success({}, message)

	def start_job(self, context):
		self.instance_id = self.parameters['instance_id']
		self.instance_path = self.configuration.get_instance_path(self.instance_id)
		self.instance_data = self.configuration.instances.get_instance(self.instance_id)

		if not os.path.exists(self.instance_path):
			# Oops. Something is out of sync.
			self.logger.error("Instance path no longer exists.")
			self.failed("Instance path no longer exists.")
			return

		self.startup_commands = list(self.instance_data['instance_type']['startup'])
		# Reverse them - we don't execute in reverse order,
		# but we do pop() them off, so this allows them to work in
		# the intended manifest supplied order.
		self.startup_commands.reverse()

		# Merge in the local environment at this stage.
		self.instance_data['environment'] = ApplicationEnvironment.merge_local_environment(
			self.configuration,
			self.instance_data['environment']
		)

		if self.instance_data['instance'].has_key('port'):
			self.instance_data['environment']['PM_PORT'] = str(self.instance_data['instance']['port'])

		# If supplied with a runtime, get that runtime to set up the environment
		# before we continue. It can be None, so check for that too.
		runtime_name = self.instance_data['instance_type']['runtime_name']
		if not self.configuration.plugins.exists(runtime_name, paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT):
			error_message = "No such runtime plugin %s" % runtime_name
			self.logger.error(error_message)
			self.failed(error_message)
		else:
			# Fetch the plugin.
			plugin = self.configuration.plugins.instantiate(
				runtime_name,
				paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT,
				{},
				self.logger
			)

			self.logger.debug("Getting runtime plugin %s to set up environment.", runtime_name)

			# Get it to set up the environment, and call our continue
			# function when ready.
			plugin.environment(
				self.instance_data['instance_type']['runtime_version'],
				self.instance_data['environment'],
				self._environment_ready,
				self._plugin_failure
			)

	# Callback for when the environment is ready.
	# This environment is used to actually fire up the instance as well.
	def _environment_ready(self, message):
		# Save the instance data. Which now includes a mutated environment.
		self.logger.info("Environment ready.");
		self.configuration.instances.save()

		# We need to go over the startup entries in order,
		# and process them, signalling failure when one fails,
		# and success when we have none left.
		# CAUTION: The environment is not shared between commands.
		if len(self.startup_commands) == 0:
			self.logger.info("No tasks to progress, so successfully completed.")
			self.done("No tasks to process.")
		else:
			self.logger.info("Running through %d tasks.", len(self.startup_commands))
			task = self.startup_commands.pop()
			self._do_startup_task(task)

	def _find_next_task(self):
		# Find the next task.
		try:
			next_task = self.startup_commands.pop()
			self._do_startup_task(next_task)
		except IndexError, ex:
			# No more tasks to pop. So we're done!
			self.logger.info("Completed all tasks successfully.")
			self.done("Completed all startup tasks successfully.")

	def _do_startup_task(self, task):
		plugin_name = task['plugin']
		if self.configuration.plugins.exists(plugin_name, paasmaker.util.plugin.MODE.RUNTIME_STARTUP):
			self.logger.info("Starting up plugin %s...", plugin_name)
			plugin = self.configuration.plugins.instantiate(
				plugin_name,
				paasmaker.util.plugin.MODE.RUNTIME_STARTUP,
				task['parameters'],
				self.logger
			)
			plugin.prepare(
				self.instance_data['environment'],
				self.instance_path,
				self._plugin_success,
				self._plugin_failure
			)
		else:
			# Invalid plugin.
			error_message ="No such startup plugin %s" % plugin_name
			self.logger.error(error_message)
			self.failed(error_message)

	def _plugin_success(self, message):
		self._find_next_task()

	def _plugin_failure(self, message):
		self.failed("Failed to execute startup command: " + message)
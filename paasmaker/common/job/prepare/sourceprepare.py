
import paasmaker
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import colander

class SourcePreparerJobParametersSchema(colander.MappingSchema):
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class SourcePreparerJob(BaseJob):
	PARAMETERS_SCHEMA = {MODE.JOB: SourcePreparerJobParametersSchema()}

	def done(self, message):
		self.success({'environment': self.environment}, message)

	def start_job(self, context):
		# This is the working directory for this.
		self.path = context['working_path']
		self.environment = context['environment']

		self.prepare_commands = list(self.parameters['data']['commands'])
		# Reverse them - we don't execute in reverse order,
		# but we do pop() them off, so this allows them to work in
		# the intended manifest supplied order.
		self.prepare_commands.reverse()

		# Callback for when the environment is ready.
		def environment_ready(message):
			# We need to go over the prepare entries in order,
			# and process them, signalling failure when one fails,
			# and success when we have none left.
			# CAUTION: The environment is not shared between commands.
			if len(self.prepare_commands) == 0:
				self.logger.info("No tasks to process, so successfully completed.")
				self.done("No tasks to process.")
			else:
				self.logger.info("Running through %d tasks.", len(self.prepare_commands))
				task = self.prepare_commands.pop()
				self.do_prepare_task(task)

		# If supplied with a runtime, get that runtime to set up the environment
		# before we continue. It can be None, so check for that too.
		runtime_data = self.parameters['data']['runtime']
		runtime_name = runtime_data['name']
		if runtime_name:
			if not self.configuration.plugins.exists(runtime_name, paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT):
				error_message = "No such runtime plugin %s" % runtime_name
				self.logger.error(error_message)
				self.failed(error_message)
				return
			else:
				# Fetch the plugin.
				plugin = self.configuration.plugins.instantiate(
					runtime_name,
					paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT,
					runtime_data['parameters'],
					self.logger
				)

				self.logger.debug("Getting plugin %s to set up environment.", runtime_name)

				# Get it to set up the environment, and call our continue
				# function when ready.
				plugin.environment(
					runtime_data['version'],
					self.environment,
					environment_ready,
					self.plugin_failure
				)
		else:
			# Skip directly to the environment ready.
			environment_ready("Ready.")

	def find_next_task(self):
		# Find the next task.
		try:
			next_task = self.prepare_commands.pop()
			self.do_prepare_task(next_task)
		except IndexError, ex:
			# No more tasks to pop. So we're done!
			self.logger.info("Completed all tasks successfully.")
			self.done("Completed all prepare tasks successfully.")

	def do_prepare_task(self, task):
		plugin_name = task['plugin']
		if self.configuration.plugins.exists(plugin_name, paasmaker.util.plugin.MODE.PREPARE_COMMAND):
			self.logger.info("Starting up plugin %s...", plugin_name)
			plugin = self.configuration.plugins.instantiate(
				plugin_name,
				paasmaker.util.plugin.MODE.PREPARE_COMMAND,
				task['parameters'],
				self.logger
			)
			plugin.prepare(self.environment, self.path, self.plugin_success, self.plugin_failure)
		else:
			# Invalid plugin.
			error_message ="No such prepare plugin %s" % plugin_name
			self.logger.error(error_message)
			self.failed(error_message)

	def plugin_success(self, message):
		self.find_next_task()

	def plugin_failure(self, message):
		self.failed("Failed to execute prepare command: " + message)
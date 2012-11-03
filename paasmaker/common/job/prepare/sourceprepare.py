
import paasmaker
from paasmaker.common.core import constants

class SourcePreparerJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration, prepare):
		self.configuration = configuration
		self.prepare_runtime = prepare['runtime']

		# Take a copy of the list, and then reverse it's order.
		# We don't execute them in reverse order, but we do
		# "pop" commands off the end, so if we reverse the list
		# first we then "pop" them off in the right order.
		self.prepare_commands = list(prepare['commands'])
		self.prepare_commands.reverse()

	def get_job_title(self):
		return "Source code preparer"

	def start_job(self):
		root = self.get_root_job()

		# This is the working directory for this.
		self.path = root.source_path
		self.environment = root.environment

		logger = self.job_logger()

		# Callback for when the environment is ready.
		def environment_ready(message):
			# We need to go over the prepare entries in order,
			# and process them, signalling failure when one fails,
			# and success when we have none left.
			# CAUTION: The environment is not shared between commands.
			if len(self.prepare_commands) == 0:
				logger.info("No tasks to progress, so successfully completed.")
				self.finished_job(constants.JOB.SUCCESS, 'No tasks to process.')
			else:
				logger.info("Running through %d tasks.", len(self.prepare_commands))
				task = self.prepare_commands.pop()
				self.do_prepare_task(task)

		# If supplied with a runtime, get that runtime to set up the environment
		# before we continue. It can be None, so check for that too.
		runtime_name = self.prepare_runtime['name']
		if runtime_name:
			if not self.configuration.plugins.exists(runtime_name, paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT):
				logger.error("No such runtime plugin %s", runtime_name)
				self.finished_job(constants.JOB.FAILED, "No such runtime plugin %s" % runtime_name)
				return
			else:
				# Fetch the plugin.
				plugin = self.configuration.plugins.instantiate(
					runtime_name,
					paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT,
					self.prepare_runtime['parameters'],
					logger
				)

				logger.debug("Getting plugin %s to set up environment.", runtime_name)

				# Get it to set up the environment, and call our continue
				# function when ready.
				plugin.environment(
					self.prepare_runtime['version'],
					self.environment,
					environment_ready,
					self.plugin_failure
				)
		else:
			# Skip directly to the environment ready.
			environment_ready("Ready.")

	def find_next_task(self):
		# Find the next task.
		logger = self.job_logger()
		try:
			next_task = self.prepare_commands.pop()
			self.do_prepare_task(next_task)
		except IndexError, ex:
			# No more tasks to pop. So we're done!
			logger.info("Completed all tasks successfully.")
			self.finished_job(constants.JOB.SUCCESS, 'Completed all prepare tasks successfully.')

	def do_prepare_task(self, task):
		logger = self.job_logger()
		plugin_name = task['plugin']
		if self.configuration.plugins.exists(plugin_name, paasmaker.util.plugin.MODE.PREPARE_COMMAND):
			logger.info("Starting up plugin %s...", plugin_name)
			plugin = self.configuration.plugins.instantiate(plugin_name, paasmaker.util.plugin.MODE.PREPARE_COMMAND, task['parameters'], logger)
			plugin.prepare(self.environment, self.path, self.plugin_success, self.plugin_failure)
		else:
			# Invalid plugin.
			logger.error("No such prepare plugin %s", plugin_name)
			self.finished_job(constants.JOB.FAILED, "No such prepare plugin %s" % plugin_name)

	def plugin_success(self, message):
		self.find_next_task()

	def plugin_failure(self, message):
		self.finished_job(constants.JOB.FAILED, message)
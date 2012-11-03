
import paasmaker
from paasmaker.common.core import constants

class SourcePreparerJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration, prepare):
		self.configuration = configuration
		# Take a copy of the list.
		self.prepare = list(prepare)
		self.prepare.reverse()

	def get_job_title(self):
		return "Source code preparer"

	def start_job(self):
		root = self.get_root_job()

		# This is the working directory for this.
		self.path = root.source_path
		self.environment = root.environment

		logger = self.job_logger()

		# We need to go over the prepare entries in order,
		# and process them, signalling failure when one fails,
		# and success when we have none left.
		# CAUTION: The environment is not shared between commands.
		if len(self.prepare) == 0:
			logger.info("No tasks to progress, so successfully completed.")
			self.finished_job(constants.JOB.SUCCESS, 'No tasks to process.')
		else:
			logger.info("Running through %d tasks.", len(self.prepare))
			task = self.prepare.pop()
			self.do_prepare_task(task)

	def find_next_task(self):
		# Find the next task.
		logger = self.job_logger()
		try:
			next_task = self.prepare.pop()
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
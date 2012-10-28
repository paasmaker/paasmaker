
import paasmaker
from paasmaker.common.core import constants

class SourceSCMJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration, parameters):
		self.configuration = configuration
		self.parameters = parameters

	def get_job_title(self):
		return "Source code SCM handler - %s" % self.parameters['method']

	def start_job(self):
		logger = self.job_logger()
		try:
			scm_plugin = self.configuration.plugins.instantiate(self.parameters['method'], self.parameters['parameters'], logger)
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			logger.critical("Failed to start a SCM plugin for %s.", self.parameters['method'])
			logger.critical(ex)
			self.finished_job(constants.JOB.FAILED, "Failed to start a SCM plugin.")
			return

		# Now that SCM plugin should create us a directory that we can work on.
		# The success callback will emit a working directory.
		# TODO: Cleanup on failure!
		scm_plugin.create_working_copy(self.scm_success, self.scm_failure)

	def scm_success(self, path, message):
		# Store the path on the root job.
		root = self.get_root_job()
		root.source_path = path

		# And signal completion.
		self.finished_job(constants.JOB.SUCCESS, message)

	def scm_failure(self, message):
		# Signal failure.
		self.finished_job(constants.JOB.FAILED, message)

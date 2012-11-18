
import paasmaker
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import colander

class SourceSCMJobParametersSchema(colander.MappingSchema):
	scm = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class SourceSCMJob(BaseJob):
	PARAMETERS_SCHEMA = {MODE.JOB: SourceSCMJobParametersSchema()}

	def start_job(self, context):
		try:
			scm_plugin = self.configuration.plugins.instantiate(
				self.parameters['scm']['method'],
				paasmaker.util.plugin.MODE.SCM_EXPORT,
				self.parameters['scm']['parameters'],
				self.logger
			)
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			error_message = "Failed to start a SCM plugin for %s.", self.parameters['method']
			logger.critical(error_message)
			logger.critical(ex)
			self.failed(error_message)
			return

		# Now that SCM plugin should create us a directory that we can work on.
		# The success callback will emit a working directory.
		# TODO: Cleanup on failure/abort
		scm_plugin.create_working_copy(self.scm_success, self.scm_failure)

	def scm_success(self, path, message):
		# Emit the path via the context.
		self.success({'working_path': path}, message)

	def scm_failure(self, message):
		# Signal failure.
		# TODO: Cleanup.
		self.failed(message)

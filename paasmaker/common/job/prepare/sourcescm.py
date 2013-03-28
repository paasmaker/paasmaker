#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import colander

class SourceSCMJobParametersSchema(colander.MappingSchema):
	scm_name = colander.SchemaNode(colander.String())
	scm_parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class SourceSCMJob(BaseJob):
	"""
	A job to fetch source code from an SCM, so it can be read and prepared.
	"""
	MODES = {
		MODE.JOB: SourceSCMJobParametersSchema()
	}

	def start_job(self, context):
		self.context = context
		try:
			self.scm_plugin = self.configuration.plugins.instantiate(
				self.parameters['scm_name'],
				paasmaker.util.plugin.MODE.SCM_EXPORT,
				self.parameters['scm_parameters'],
				self.logger
			)
		except paasmaker.util.configurationhelper.InvalidConfigurationFormatException, ex:
			error_message = "Failed to start a SCM plugin for %s.", self.parameters['scm_name']
			self.logger.critical(error_message, exc_info=ex)
			self.failed(error_message)
			return

		# Now that SCM plugin should create us a directory that we can work on.
		# The success callback will emit a working directory.
		# TODO: Cleanup on failure/abort.
		self.scm_plugin.create_working_copy(self.scm_success, self.scm_failure)

	def scm_success(self, path, message, parameters={}):
		# Emit the path via the context.
		parameters['manifest_path'] = self.context['manifest_path']
		self.success({'working_path': path, 'scm_output': parameters}, message)

	def scm_failure(self, message):
		# Signal failure.
		# TODO: Cleanup.
		self.failed(message)

	def abort_job(self):
		# Ask the plugin to stop.
		# It should exit with an error of some kind.
		if hasattr(self, 'scm_plugin'):
			self.scm_plugin.abort()
		# Otherwise, do nothing.

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE
from ...testhelpers import TestHelpers

import colander

class ServiceImportJobParametersSchema(colander.MappingSchema):
	import_file = colander.SchemaNode(
		colander.String(),
		title="File to import",
		description="Full path to the file to import."
	)
	service_id = colander.SchemaNode(
		colander.Integer(),
		title="Service ID",
		description="The service database ID to import into."
	)
	parameters = colander.SchemaNode(
		colander.Mapping(unknown='preserve'),
		title="Parameters",
		description="Parameters for the service importer, if required.",
		missing={},
		default={}
	)
	delete_after_import = colander.SchemaNode(
		colander.Boolean(),
		title="Delete import file once complete",
		description="If true, delete the import file on a successful import.",
		default=False,
		missing=False
	)

class ServiceImportJob(BaseJob):
	"""
	A job to import the contents of a service.
	"""
	MODES = {
		MODE.JOB: ServiceImportJobParametersSchema()
	}

	def start_job(self, context):
		if not os.path.exists(self.parameters['import_file']):
			error_msg = "No such file %s" % self.parameters['import_file']
			self.logger.error(error_msg)
			self.failed(error_msg)
			return

		def got_session(session):
			service = session.query(
				paasmaker.model.Service
			).get(
				self.parameters["service_id"]
			)

			if service is None:
				error_msg = "Can't find service %d to import into." % self.parameters["service_id"]
				session.close()
				self.logger.error(error_msg)
				self.failed(error_msg)
				return

			can_import = self.configuration.plugins.exists(
				service.provider,
				paasmaker.util.plugin.MODE.SERVICE_IMPORT
			)

			if not can_import:
				error_msg = "Service provider %s doesn't support importing." % service.provider
				session.close()
				self.logger.error(error_msg)
				self.failed(error_msg)
				return

			# Store the provider and credentials.
			self.service_name = service.name
			self.credentials = service.credentials
			self.provider = service.provider

			# And we're done with the session.
			session.close()

			# Start the process.
			self._start_importing()

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

	def _start_importing(self):
		# Get an instance of the plugin.
		self.plugin = self.configuration.plugins.instantiate(
			self.provider,
			paasmaker.util.plugin.MODE.SERVICE_IMPORT,
			self.parameters['parameters'],
			logger=self.logger
		)

		# Commence the import.
		self.plugin.import_file(
			self.service_name,
			self.credentials,
			self.parameters['import_file'],
			self._complete,
			self._error
		)

	def _complete(self, message):
		# Now we're done!
		self.logger.info(message)

		# Do we want to delete the import file?
		if self.parameters['delete_after_import']:
			def remove_complete(code):
				# Just continue regardless of the response code.
				self.logger.info("Removal finished with code %d.", code)
				self._really_complete()

			# Do this in a subprocess, as it may take some time.
			self.logger.info("Removing imported file...")
			remover = paasmaker.util.popen.Popen(
				['rm', self.parameters['import_file']],
				on_exit=remove_complete,
				io_loop=self.configuration.io_loop
			)
		else:
			self._really_complete()

	def _really_complete(self):
		self.success({}, "Successfully imported.")

	def _error(self, message, exception=None):
		self.logger.error(message)
		if exception is not None:
			self.logger.error("Exception:", exc_info=exception)
		self.failed(message)

	def abort_job(self):
		# Ask the plugin to cancel. This will fire off the error callback
		# and then abort the job.
		if hasattr(self, 'plugin'):
			self.plugin.import_cancel()

	@classmethod
	def setup_for_service(cls, configuration, service, filename, callback, delete_after_import=False):
		tags = [
			'workspace:%d' % service.application.workspace.id,
			'application:%d' % service.application.id
		]

		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.service.import',
			{
				'service_id': service.id,
				'import_file': filename,
				'delete_after_import': delete_after_import
			},
			"Import into service %s" % service.name,
			tags=tags
		)

		def on_tree_added(root_id):
			callback(root_id)

		# Add that entire tree into the job manager.
		configuration.job_manager.add_tree(tree, on_tree_added)
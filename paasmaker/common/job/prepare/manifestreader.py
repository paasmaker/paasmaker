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
from paasmaker.common.core import constants
from ..base import BaseJob

from paasmaker.util.configurationhelper import InvalidConfigurationParameterException
from paasmaker.util.configurationhelper import InvalidConfigurationFormatException

import sqlalchemy

class ManifestReaderJob(BaseJob):
	"""
	A job to read the application manifest, and spawn other jobs based on that
	manifest. For example, it will spawn jobs to create services as required.
	"""

	def start_job(self, context):
		output_context = {}
		manifest_full_path = os.path.join(context['working_path'], context['manifest_path'])
		self.logger.debug("About to start reading manifest from file %s", manifest_full_path)

		# Load the manifest.
		manifest = paasmaker.common.application.configuration.ApplicationConfiguration(self.configuration)
		try:
			manifest.load_from_file([manifest_full_path])
		except (InvalidConfigurationParameterException, InvalidConfigurationFormatException), ex:
			self.logger.critical("Failed to load configuration:")
			self.logger.critical("Exception:", exc_info=ex)
			self.failed("Failed to load configuration.")
			return

		def got_session(session):
			# Now based on that successul loading of the manifest, get started.
			workspace = session.query(
				paasmaker.model.Workspace
			).get(
				context['workspace_id']
			)

			if not context['application_id']:
				# New application.
				self.logger.debug("Creating new application for manifest.")

				# See if the application already exists.
				application_name = manifest.get_flat('application.name')
				existing = session.query(
					paasmaker.model.Application
				).filter(
					paasmaker.model.Application.name == application_name,
					paasmaker.model.Application.workspace == workspace
				).first()

				if existing:
					# Let's create a new version of the application instead then.
					self.logger.debug("Creating a new version of the application.")
					application = existing
				else:
					self.logger.debug("Creating new application.")
					application = manifest.create_application(session, workspace)
			else:
				self.logger.debug("Using existing application for manifest.")
				application = session.query(paasmaker.model.Application).get(context['application_id'])

			self.logger.debug("Unpacking manifest into database...")
			try:
				scm_full_parameters = dict(context['scm_parameters'])
				if 'scm_output' in context:
					scm_full_parameters.update(context['scm_output'])
					if 'preferred_packer' in scm_full_parameters:
						output_context['preferred_packer'] = scm_full_parameters['preferred_packer']
					if 'preferred_storer' in scm_full_parameters:
						output_context['preferred_storer'] = scm_full_parameters['preferred_storer']

				application_version = manifest.unpack_into_database(
					session,
					application,
					context['scm_name'],
					scm_full_parameters
				)
			except sqlalchemy.exc.IntegrityError, ex:
				self.logger.error("Failed to unpack into database.", exc_info=True)
				self.failed("Failed to unpack into database.")
				return

			# Persist it all now so we have a record for later.
			session.add(application_version)
			session.commit()

			# Store the results in the context.
			output_context['application_id'] = application.id
			output_context['application_version_id'] = application_version.id

			# Set up depending jobs for preparing sources.
			self.logger.info("Preparing jobs based on Manifest.")

			# We're trying to end up with a job tree like below:
			# Root job
			# - Manifest reader
			# - Packer
			#   - Preparer
			#     - Service Container
			#       - Service A
			#       - Service B
			# Because the jobs execute from the leaf first,
			# the services will execute first (in parallel),
			# then the packer and preparer once both of those
			# are complete.

			# Add some extra tags to the root job.
			tags = []
			tags.append('application:%d' % application.id)
			tags.append('application_version:%d' % application_version.id)

			tree = self.configuration.job_manager.get_specifier()
			tree.set_job(
				'paasmaker.job.prepare.packer',
				{},
				'Package source code',
				tags=tags
			)

			# Add the preparer.
			preparer = tree.add_child()
			preparer.set_job(
				'paasmaker.job.prepare.preparer',
				{
					'data': manifest['application']['prepare']
				},
				'Prepare source code'
			)

			servicecontainer = preparer.add_child()
			servicecontainer.set_job(
				'paasmaker.job.prepare.servicecontainer',
				{},
				'Services'
			)

			for service in application_version.services:
				plugin_exists = self.configuration.plugins.exists(
					service.provider,
					paasmaker.util.plugin.MODE.SERVICE_CREATE
				)
				if not plugin_exists:
					error_message = "No service provider %s found." % service.provider
					self.logger.critical(error_message)
					self.failed(error_message)
					return
				else:
					servicejob = servicecontainer.add_child()
					servicejob.set_job(
						'paasmaker.job.prepare.service',
						{
							'service_id': service.id
						},
						"Create or update service '%s'" % service.name
					)

			def on_tree_executable():
				self.success(output_context, "Created all prepare jobs.")

			def on_tree_added(root_id):
				self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

			# Add that entire tree into the job manager.
			session.close()
			self.configuration.job_manager.add_tree(tree, on_tree_added, parent=self.job_metadata['root_id'])

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)
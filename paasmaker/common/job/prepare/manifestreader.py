
import os

import paasmaker
from paasmaker.common.core import constants
from paasmaker.common.core import constants
from ..base import BaseJob

import sqlalchemy

class ManifestReaderJob(BaseJob):

	def start_job(self, context):
		self.output_context = {}
		manifest_full_path = os.path.join(context['working_path'], context['manifest_path'])
		self.logger.debug("About to start reading manifest from file %s", manifest_full_path)

		# Load the manifest.
		self.manifest = paasmaker.common.application.configuration.ApplicationConfiguration()
		try:
			self.manifest.load_from_file([manifest_full_path])
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			self.logger.critical("Failed to load configuration:")
			self.logger.critical(exc_info=ex)
			self.failed("Failed to load configuration.")
			return

		# Now based on that successul loading of the manifest, get started.
		session = self.configuration.get_database_session()
		workspace = session.query(paasmaker.model.Workspace).get(context['workspace_id'])
		if not context['application_id']:
			# New application.
			self.logger.debug("Creating new application for manifest.")

			# See if the application already exists.
			application_name = self.manifest.get_flat('application.name')
			existing = session.query(
				paasmaker.model.Application
			).filter(
				paasmaker.model.Application.name == application_name,
				paasmaker.model.Application.workspace == workspace
			).first()

			if existing:
				error_message = "Application %s already exists in this workspace." % application_name
				self.logger.error(error_message)
				self.failed(error_message)
				return

			application = self.manifest.create_application(session, workspace)
		else:
			self.logger.debug("Using existing application for manifest.")
			application = session.query(paasmaker.model.Application).get(context['application_id'])

		self.logger.debug("Unpacking manifest into database...")
		try:
			application_version = self.manifest.unpack_into_database(
				session,
				application,
				context['scm_name'],
				context['scm_parameters']
			)
		except sqlalchemy.exc.IntegrityError, ex:
			self.logger.error("Failed to unpack into database.", exc_info=True)
			self.failed("Failed to unpack into database.")
			return

		# Persist it all now so we have a record for later.
		session.add(application_version)
		session.commit()

		# Store the results in the context.
		self.output_context['application_id'] = application.id
		self.output_context['application_version_id'] = application_version.id

		# Set up depending jobs for preparing sources.
		self.logger.info("Preparing jobs based on Manifest.")

		# Check all the services first to make sure they exist
		# This allows us to fail earlier.
		self.destroyable_service_list = []
		for service in application_version.services:
			if not self.configuration.plugins.exists(service.provider, paasmaker.util.plugin.MODE.SERVICE_CREATE):
				error_message = "No service provider %s found.", service.provider
				self.logger.critical(error_message)
				self.failed(error_message)
				return
			else:
				self.destroyable_service_list.append(service)

		# Fetch out the root job ID for convenience.
		self.root_job_id = self.job_metadata['root_id']

		# We're trying to end up with a job tree like below:
		# Root job
		# - Manifest reader
		# - Packer
		#   - Preparer
		#     - Service Container
		#       - Service A
		#       - Service B
		# Because the jobs execute from the leaf first,
		# the services will execute first (in paralell),
		# then the packer and preparer once both of those
		# are complete.

		# Add some extra tags to the root job.
		tags = []
		tags.append('application:%d' % application.id)
		tags.append('application_version:%d' % application_version.id)

		# Add the packer job, which starts off the process.
		self.configuration.job_manager.add_job(
			'paasmaker.job.prepare.packer',
			{},
			'Package source code',
			parent=self.root_job_id,
			callback=self.on_packer_added,
			tags=tags
		)

	def on_packer_added(self, packer_job_id):
		# Add the preparer.
		self.configuration.job_manager.add_job(
			'paasmaker.job.prepare.preparer',
			{'data': self.manifest['application']['prepare']},
			'Prepare source code',
			parent=packer_job_id,
			callback=self.on_preparer_added
		)

	def on_preparer_added(self, preparer_job_id):
		# Also add the service container, and then services themselves.
		self.configuration.job_manager.add_job(
			'paasmaker.job.prepare.servicecontainer',
			{},
			'Services',
			parent=preparer_job_id,
			callback=self.on_service_container_added
		)

	def on_service_container_added(self, service_container_job_id):
		# Queue up all the services.
		def create_service(service):
			def create_service_queued(queued_service_id):
				try:
					next_service = self.destroyable_service_list.pop()
					create_service(next_service)
				except IndexError, ex:
					# No more services to create.
					# So signal completion.
					self.on_prepare_complete()
				# end create_service_queued()

			self.configuration.job_manager.add_job(
				'paasmaker.job.prepare.service',
				{'service_id': service.id},
				"Create or update service '%s'" % service.name,
				parent=service_container_job_id,
				callback=create_service_queued
			)
			# end create_service()

		if len(self.destroyable_service_list) == 0:
			# No jobs. Proceed to prepare.
			self.on_prepare_complete()
		else:
			# Kick off the service job add process.
			create_service(self.destroyable_service_list.pop())

	def on_prepare_complete(self):
		## KICKOFF
		# At this stage, all the code following has executed it's callbacks to get to
		# here. So now we can make our jobs executable and let them run wild.
		self.configuration.job_manager.allow_execution(self.job_id, callback=self.on_execution_allowed)

	def on_execution_allowed(self):
		# Success! All queued up.
		self.success(self.output_context, "Set up tasks all queued.")
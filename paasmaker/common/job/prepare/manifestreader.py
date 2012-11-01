
import paasmaker
from paasmaker.common.core import constants
from packer import SourcePackerJob
from service import ServiceJob, ServiceContainerJob
from sourceprepare import SourcePreparerJob
from sourcescm import SourceSCMJob
from paasmaker.common.core import constants

class ManifestReaderJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration):
		self.configuration = configuration

	def get_job_title(self):
		return "Application manifest reader and unpacker"

	def start_job(self):
		# HACK: The root job contains all the context we need.
		# For discussion: if this hack is bad or not.
		root = self.get_root_job()

		# Get a logger.
		logger = self.job_logger()
		logger.debug("About to start reading manifest from file %s", root.manifest)

		# Load the manifest.
		self.manifest = paasmaker.common.application.configuration.ApplicationConfiguration()
		try:
			self.manifest.load_from_file([root.manifest])
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			logger.critical("Failed to load configuration:")
			logger.critical(ex)
			self.finished_job(constants.JOB.FAILED, "Failed to load configuration.")
			return

		# Check that the source SCM exists.
		if not self.configuration.plugins.exists(self.manifest['application']['source']['method'], paasmaker.util.plugin.MODE.SCM_EXPORT):
			logger.critical("SCM plugin %s does not exist.", self.manifest['application']['source']['method'])
			self.finished_job(constants.JOB.FAILED, "SCM plugin %s does not exist." % self.manifest['application']['source']['method'])

		# If the file is uploaded, inject it into the manifest.
		if root.uploaded_file:
			logger.debug("Setting uploaded file: %s", root.uploaded_file)
			self.manifest.set_upload_location(root.uploaded_file)

		# Now based on that successul loading of the manifest, get started.
		if not root.application:
			# New application.
			logger.debug("Creating new application for manifest.")
			root.application = self.manifest.create_application(root.session, root.workspace)
		else:
			logger.debug("Using existing application for manifest.")

		logger.debug("Unpacking manifest into database...")
		root.version = self.manifest.unpack_into_database(root.session, root.application)

		# Persist it all now so we have a record for later.
		root.session.add(root.version)
		root.session.commit()

		# Set up depending jobs for preparing sources.
		logger.debug("Preparing jobs.")
		source_preparer = SourcePreparerJob(self.configuration, self.manifest['application']['source']['prepare'])
		source_scm = SourceSCMJob(self.configuration, self.manifest['application']['source'])
		service_root = ServiceContainerJob(self.configuration)
		packer = SourcePackerJob(self.configuration)

		# TODO: Add a configurable uploader job.

		# Add base children jobs.
		manager = self.configuration.job_manager
		manager.add_job(source_preparer)
		manager.add_job(source_scm)
		# We always add a service root job, even if there are no services
		# as it sets up the environment for prepare runs.
		manager.add_job(service_root)
		manager.add_job(packer)

		manager.add_child_job(root, packer)
		manager.add_child_job(packer, source_preparer)
		manager.add_child_job(source_preparer, source_scm)
		manager.add_child_job(source_preparer, service_root)

		# For each service, check that it has a matching provider,
		# and that the parameters passed are valid.
		for service in root.version.services:
			if not self.configuration.plugins.exists(service.provider, paasmaker.util.plugin.MODE.SERVICE_CREATE):
				logger.critical("No service provider %s found.", service.provider)
				self.finished_job(constants.JOB.FAILED, "Bad service provider supplied.")
				return

			# Create a job for it.
			service_job = ServiceJob(self.configuration, service)
			manager.add_job(service_job)
			manager.add_child_job(service_root, service_job)

		# So now we're all queued up.
		# Mark this job as finished, which causes the other queued jobs to commence executing.
		logger.debug("All jobs set up, signalling startup for those jobs.")
		self.finished_job(constants.JOB.SUCCESS, 'Successfully queued up other tasks.')

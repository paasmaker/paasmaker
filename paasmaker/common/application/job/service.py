
import json

import paasmaker
from paasmaker.common.core import constants

class ServiceContainerJob(paasmaker.util.jobmanager.ContainerJob):
	def __init__(self, configuration):
		self.configuration = configuration

	def get_job_title(self):
		return "Service container"

	def start_job(self):
		# Fetch all the relevant services and put them into the environment
		# for the prepare tasks.
		root = self.get_root_job()

		credentials = root.version.get_service_credentials()

		root.environment['PM_SERVICES'] = json.dumps(credentials)

		# And signal success so the prepare jobs can start.
		self.finished_job(constants.JOB.SUCCESS, 'All services prepared.')

class ServiceJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration, service):
		self.configuration = configuration
		self.service = service

	def get_job_title(self):
		return "Service create for %s (provider %s)" % (self.service.name, self.service.provider)

	def start_job(self):
		root = self.get_root_job()

		try:
			service_plugin = self.configuration.plugins.instantiate(self.service.provider, paasmaker.util.plugin.MODE.SERVICE_CREATE, self.service.parameters, self.job_logger())
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			logger.critical("Failed to start a service plugin for %s.", self.service.provider)
			logger.critical(ex)
			self.finished_job(constants.JOB.FAILED, "Failed to start a service plugin.")
			return

		# Get this service plugin to create it's service.
		if self.service.state == constants.SERVICE.NEW:
			service_plugin.create(self.service_success, self.service_failure)
		else:
			service_plugin.update(self.service_success, self.service_failure)

	def service_success(self, credentials, message):
		root = self.get_root_job()

		root.session.refresh(self.service)

		# Record the new state.
		self.service.credentials = credentials
		self.service.state = constants.SERVICE.AVAILABLE
		root.session.add(self.service)
		root.session.commit()

		# And signal completion.
		self.finished_job(constants.JOB.SUCCESS, message)

	def service_failure(self, message):
		root = self.get_root_job()

		root.session = self.configuration.get_database_session()

		# Record the new state.
		self.service.credentials = credentials
		self.service.state = constants.SERVICE.ERROR
		root.session.add(self.service)
		root.session.commit()

		# Signal failure.
		self.finished_job(constants.JOB.FAILED, message)

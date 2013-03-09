
import json

import paasmaker
from paasmaker.common.core import constants
from paasmaker.common.application.environment import ApplicationEnvironment
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import colander

class ServiceJobParametersSchema(colander.MappingSchema):
	service_id = colander.SchemaNode(colander.Integer())

class ServiceContainerJob(BaseJob):
	"""
	A container job to build the environment for a set of created services.
	"""
	def start_job(self, context):
		# Fetch all the relevant services and put them into the environment
		# for the prepare tasks.
		session = self.configuration.get_database_session()
		version = session.query(
			paasmaker.model.ApplicationVersion
		).get(
			context['application_version_id']
		)

		# Build our environment for later.
		environment = ApplicationEnvironment.get_environment(self.configuration, version)

		# And signal success so the prepare jobs can start.
		session.close()
		self.success({'environment': environment}, "All services created and updated.")

class ServiceJob(BaseJob):
	"""
	A job to create services during application preparation.
	"""
	MODES = {
		MODE.JOB: ServiceJobParametersSchema()
	}

	def start_job(self, context):
		self.session = self.configuration.get_database_session()
		self.service = self.session.query(
			paasmaker.model.Service
		).get(
			self.parameters['service_id']
		)

		try:
			service_plugin = self.configuration.plugins.instantiate(
				self.service.provider,
				paasmaker.util.plugin.MODE.SERVICE_CREATE,
				self.service.parameters,
				self.logger
			)
		except paasmaker.common.configuration.InvalidConfigurationException, ex:
			error_message = "Failed to start a service plugin for %s." % self.service.provider
			self.logger.critical(error_message)
			self.logger.critical(ex)
			self.failed(error_message)
			return

		# Get this service plugin to create it's service.
		if self.service.state == constants.SERVICE.NEW:
			service_plugin.create(self.service.name, self.service_success, self.service_failure)
		else:
			service_plugin.update(self.service.name, self.service.credentials, self.service_success, self.service_failure)

	def service_success(self, credentials, message):
		self.session.refresh(self.service)

		# Record the new state.
		self.service.credentials = credentials
		self.service.state = constants.SERVICE.AVAILABLE
		self.session.add(self.service)
		self.session.commit()

		# And signal completion.
		self.success({}, "Successfully created service %s" % self.service.name)

	def service_failure(self, message):
		# Record the new state.
		self.session.refresh(self.service)
		self.service.credentials = credentials
		self.service.state = constants.SERVICE.ERROR
		self.session.add(self.service)
		self.session.commit()

		# Signal failure.
		self.failed(message)

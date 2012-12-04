import unittest
import uuid
import logging
import json
import os
import tempfile

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class VersionRootController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_version(self, version_id):
		version = self.db().query(paasmaker.model.ApplicationVersion).get(int(version_id))
		if not version:
			raise tornado.web.HTTPError(404, "No such version.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=version.application.workspace)
		return version

class VersionController(VersionRootController):
	def get(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		# For the API, fetch a list of types as well.
		types = {}
		for instance_type in version.instance_types:
			types[instance_type.name] = instance_type
		self.add_data('types', types)

		self.render("version/view.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)", VersionController, configuration))
		return routes

class VersionInstancesController(VersionRootController):
	def get(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		# For the API, fetch a list of types as well,
		# and then instances per type for that.
		instances = {}
		for instance_type in version.instance_types:
			data = {}
			data['instance_type'] = instance_type
			data['instances'] = instance_type.instances
			instances[instance_type.name] = data
		self.add_data('instances', instances)

		self.render("version/instances.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/instances", VersionInstancesController, configuration))
		return routes

class VersionRegisterController(VersionRootController):

	@tornado.web.asynchronous
	def post(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		def on_job_started():
			self.add_data_template('generic_title', 'Registering instances')
			self.render("job/genericstart.html")
			self.finish()

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.registerroot.RegisterRootJob.setup_version(
			self.configuration,
			version,
			on_root_added
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/register", VersionRegisterController, configuration))
		return routes

class VersionStartupController(VersionRootController):

	@tornado.web.asynchronous
	def post(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		def on_job_started():
			self.add_data_template('generic_title', 'Starting instances')
			self.render("job/genericstart.html")
			self.finish()

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.startuproot.StartupRootJob.setup_version(
			self.configuration,
			version,
			on_root_added
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/start", VersionStartupController, configuration))
		return routes

class VersionShutdownController(VersionRootController):

	@tornado.web.asynchronous
	def post(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		def on_job_started():
			self.add_data_template('generic_title', 'Shutting down instances')
			self.render("job/genericstart.html")
			self.finish()

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.shutdownroot.ShutdownRootJob.setup_version(
			self.configuration,
			version,
			on_root_added
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/stop", VersionShutdownController, configuration))
		return routes

class VersionDeRegisterController(VersionRootController):

	@tornado.web.asynchronous
	def post(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		def on_job_started():
			self.add_data_template('generic_title', 'De registering instances')
			self.render("job/genericstart.html")
			self.finish()

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.deregisterroot.DeRegisterRootJob.setup_version(
			self.configuration,
			version,
			on_root_added
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/deregister", VersionDeRegisterController, configuration))
		return routes
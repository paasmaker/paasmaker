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
		if version.deleted:
			raise tornado.web.HTTPError(404, "Deleted version.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=version.application.workspace)
		return version

class VersionController(VersionRootController):

	@tornado.web.asynchronous
	def get(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)
		self.add_data_template('configuration', self.configuration)

		# For the API, fetch a list of types as well.
		types = {}
		for instance_type in version.instance_types:
			types[instance_type.name] = instance_type.flatten()
			types[instance_type.name]['version_url'] = instance_type.version_hostname(self.configuration)
		self.add_data('types', types)

		# Fetch the router stats.
		self._get_router_stats_for('version', version.id, self._got_stats)

	def _got_stats(self, result):
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

		# TODO: This prevents us from being able to add new
		# instances if the instances have errors. Rethink this.
		if version.state != constants.VERSION.PREPARED:
			self.add_error("Version must be in state PREPARED to be registered.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		self.add_data('version', version)

		def on_job_started():
			self._redirect_job(self.get_data('job_id'), '/application/%d' % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.register.RegisterRootJob.setup_version(
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

		if version.state != constants.VERSION.READY and version.state != constants.VERSION.PREPARED:
			self.add_error("Version must be in state PREPARED or READY to be started.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self._redirect_job(self.get_data('job_id'), '/application/%d' % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.startup.StartupRootJob.setup_version(
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

		if version.state != constants.VERSION.RUNNING:
			self.add_error("Version must be in state RUNNING to be stopped.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self._redirect_job(self.get_data('job_id'), '/application/%d' % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.shutdown.ShutdownRootJob.setup_version(
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

		if version.state != constants.VERSION.READY:
			self.add_error("Version must be in state READY to be de-registered.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self._redirect_job(self.get_data('job_id'), '/application/%d' % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.deregister.DeRegisterRootJob.setup_version(
			self.configuration,
			version,
			on_root_added
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/deregister", VersionDeRegisterController, configuration))
		return routes

class VersionDeleteController(VersionRootController):

	@tornado.web.asynchronous
	def post(self, version_id):
		version = self._get_version(version_id)
		self.add_data('version', version)

		if version.is_current:
			self.add_error("The current version cannot be deleted. Make another version current before deleting this one.")
			raise tornado.web.HTTPError(400, "Can't delete current version.")

		if version.state != constants.VERSION.PREPARED:
			self.add_error("Version must be in state PREPARED to be deleted.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		# TODO: Remove files off disk or other systems.

		version.delete()
		self.db().add(version)
		self.db().commit()

		self.redirect("/application/%d" % version.application.id)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/delete", VersionDeleteController, configuration))
		return routes
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
		version = self.session.query(
			paasmaker.model.ApplicationVersion
		).get(int(version_id))
		if not version:
			raise tornado.web.HTTPError(404, "No such version.")
		if version.deleted:
			raise tornado.web.HTTPError(404, "Deleted version.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=version.application.workspace)
		return version

	def _get_instance_type(self, instance_type_id):
		instance_type = self.session.query(
			paasmaker.model.ApplicationInstanceType
		).get(int(instance_type_id))

		if not instance_type:
			raise tornado.web.HTTPError(404, "No such instance type.")
		if instance_type.deleted:
			raise tornado.web.HTTPError(404, "Deleted instance type.")

		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=instance_type.application_version.application.workspace)

		return instance_type

class VersionController(VersionRootController):

	def get(self, version_id):
		version = self._get_version(version_id)
		self.add_data_template('configuration', self.configuration)

		self.add_data('version', version)
		self.add_data('application', version.application)
		self.add_data('workspace', version.application.workspace)

		self.add_data('frontend_domain_postfix', self.configuration.get_flat('pacemaker.frontend_domain_postfix'))

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)", VersionController, configuration))
		return routes

class VersionInstancesController(VersionRootController):

	def get(self, version_id):
		version = self._get_version(version_id)

		# For the API, fetch a list of types as well,
		# and then instances per type for that.
		instances = {}
		for instance_type in version.instance_types:
			data = {}
			data['instance_type'] = instance_type.flatten()
			data['instance_type']['version_url'] = instance_type.version_hostname(self.configuration)
			data['instances'] = instance_type.instances
			instances[instance_type.name] = data
		self.add_data('instances', instances)

		self.render("version/instances.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/instances", VersionInstancesController, configuration))
		return routes

class VersionManifestController(VersionRootController):

	def get(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_VIEW_MANIFEST, workspace=version.application.workspace)

		self.add_data('version', version)
		self.add_data('manifest', version.manifest)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/manifest", VersionManifestController, configuration))
		return routes

class VersionRegisterController(VersionRootController):

	def post(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_DEPLOY, workspace=version.application.workspace)

		# TODO: This prevents us from being able to add new
		# instances if the instances have errors. Rethink this.
		if version.state != constants.VERSION.PREPARED:
			self.add_error("Version must be in state PREPARED to be registered.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		self.add_data('version', version)

		def on_job_started():
			self.action_success(self.get_data('job_id'), "/application/%d" % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.register.RegisterRootJob.setup_version(
			self.configuration,
			version,
			on_root_added,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/register", VersionRegisterController, configuration))
		return routes

class VersionStartupController(VersionRootController):

	def post(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_DEPLOY, workspace=version.application.workspace)

		self.add_data('version', version)

		if version.state != constants.VERSION.READY and version.state != constants.VERSION.PREPARED:
			self.add_error("Version must be in state PREPARED or READY to be started.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self.action_success(self.get_data('job_id'), "/application/%d" % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.startup.StartupRootJob.setup_version(
			self.configuration,
			version,
			on_root_added,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/start", VersionStartupController, configuration))
		return routes

class VersionShutdownController(VersionRootController):

	def post(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_DEPLOY, workspace=version.application.workspace)

		self.add_data('version', version)

		if version.state != constants.VERSION.RUNNING:
			self.add_error("Version must be in state RUNNING to be stopped.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self.action_success(self.get_data('job_id'), "/application/%d" % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.shutdown.ShutdownRootJob.setup_version(
			self.configuration,
			version,
			on_root_added,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/stop", VersionShutdownController, configuration))
		return routes

class VersionDeRegisterController(VersionRootController):

	def post(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_DEPLOY, workspace=version.application.workspace)

		self.add_data('version', version)

		if version.state != constants.VERSION.READY:
			self.add_error("Version must be in state READY to be de-registered.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		def on_job_started():
			self.action_success(self.get_data('job_id'), "/application/%d" % version.application.id)

		def on_root_added(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=on_job_started)

		paasmaker.common.job.coordinate.deregister.DeRegisterRootJob.setup_version(
			self.configuration,
			version,
			on_root_added,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/deregister", VersionDeRegisterController, configuration))
		return routes

class VersionDeleteController(VersionRootController):

	def post(self, version_id):
		version = self._get_version(version_id)
		self.require_permission(constants.PERMISSION.APPLICATION_DELETE, workspace=version.application.workspace)
		self.add_data('version', version)

		if version.is_current:
			self.add_error("The current version cannot be deleted. Make another version current before deleting this one.")
			raise tornado.web.HTTPError(400, "Can't delete current version.")

		if version.state not in [constants.VERSION.PREPARED, constants.VERSION.NEW]:
			self.add_error("Version must be in state PREPARED to be deleted.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		# TODO: Remove files off disk or other systems.

		version.delete()
		self.session.add(version)
		self.session.commit()

		self.action_success(None, "/application/%d" % version.application.id)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/delete", VersionDeleteController, configuration))
		return routes

class VersionInstanceTypeUpdateQuantitySchema(colander.MappingSchema):
	quantity = colander.SchemaNode(colander.Integer(),
		title="Quantity",
		description="The quantity of instances of the type that you want.",
		validator=colander.Range(min=1))

class VersionInstanceTypeChangeCountController(VersionRootController):

	def post(self, instance_type_id):
		instance_type = self._get_instance_type(instance_type_id)

		# Check permissions.
		# You need APPLICATION_CREATE, because you can adjust the instance
		# count also by updating the manifest file.
		self.require_permission(
			constants.PERMISSION.APPLICATION_CREATE,
			workspace=instance_type.application_version.application.workspace
		)

		# Validate date.
		valid_data = self.validate_data(VersionInstanceTypeUpdateQuantitySchema())
		if not valid_data:
			# TODO: This is a catch for HTML requests.
			# Supply back a much nicer error, and probably refill forms and stuff.
			raise tornado.web.HTTPError(400, "Invalid parameters")

		# Actually update the count.
		instance_type.quantity = int(self.params['quantity'])
		self.session.add(instance_type)
		self.session.commit()

		# TODO: Unit test.
		def job_started():
			# Redirect to clear the post.
			self._redirect_job(self.get_data('job_id'), '/version/%d' % instance_type.application_version.id)

		def startup_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		# Launch off a job to start the instance.
		# This will add new instances if you increased it.
		# If you decreased it, the health manager will kick in and
		# reduce the number of instances for us.
		paasmaker.common.job.coordinate.startup.StartupRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			startup_job_ready,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/instancetype/(\d+)/quantity", VersionInstanceTypeChangeCountController, configuration))
		return routes
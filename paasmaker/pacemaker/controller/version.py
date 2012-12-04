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

		self.render("version/instances.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/version/(\d+)/instances", VersionInstancesController, configuration))
		return routes
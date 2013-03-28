#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import json
import time

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import colander

class ConfigurationDumpController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		# Dump out the configuration.
		self.add_data('configuration', self.configuration)
		self.add_data_template('json', json)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/configuration/dump", ConfigurationDumpController, configuration))
		return routes

class PluginInformationController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		# Dump out the configuration.
		plugin_data = self.configuration.plugins.plugin_information()
		self.add_data('plugins', plugin_data)
		self.add_data_template('json', json)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/configuration/plugins", PluginInformationController, configuration))
		return routes

class ConfigurationDumpControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ConfigurationDumpController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		request = self.fetch_with_user_auth('http://localhost:%d/configuration/dump?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertIn(str(self.configuration.get_flat('redis.table.port')), response.body)

class PluginInformationControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = PluginInformationController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		request = self.fetch_with_user_auth('http://localhost:%d/configuration/plugins?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertIn('Placement', response.body)
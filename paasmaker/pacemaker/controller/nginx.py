
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado

class NginxController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		# Create a NGINX config based on this configuration.
		configuration = paasmaker.router.router.NginxRouter.get_nginx_config(self.configuration)
		self.add_data('configuration', configuration)

		self.render("nginx/configuration.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/nginx", NginxController, configuration))
		return routes

class NginxControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = NginxController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		request = self.fetch_with_user_auth('http://localhost:%d/nginx?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertIn(str(self.configuration.get_flat('redis.table.port')), response.body)
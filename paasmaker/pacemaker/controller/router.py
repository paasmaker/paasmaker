
import json
import time

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import colander

class TableDumpController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	@tornado.web.asynchronous
	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		def on_dump_complete(table, serial):
			self.add_data('table', table)
			self.add_data('serial', serial)
			self.render("router/dump.html")

		def on_dump_error(error, exception=None):
			self.add_error(error)
			self.write_error(500)

		# Dump the routing table.
		dumper = paasmaker.router.tabledump.RouterTableDump(self.configuration, on_dump_complete, on_dump_error)
		dumper.dump()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/router/dump", TableDumpController, configuration))
		return routes

class TableDumpControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = TableDumpController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		request = self.fetch_with_user_auth('http://localhost:%d/router/dump?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertIn('table', response.body)
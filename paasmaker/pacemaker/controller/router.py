
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest, BaseWebsocketHandler
from paasmaker.common.core import constants

import tornado
import colander

class NginxController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		# Create a NGINX config based on this configuration.
		configuration = paasmaker.router.router.NginxRouter.get_nginx_config(self.configuration)
		self.add_data('configuration', configuration)

		self.render("router/configuration.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/router/nginx", NginxController, configuration))
		return routes

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

class RouterStatsRequestSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Name of stats requested",
		description="The name of the stats requested (eg, workspace, application, etc)")
	input_id = colander.SchemaNode(colander.String(),
		title="The input ID",
		description="The input ID of the stats requested (eg, workspace ID, application ID, etc)")

# TODO: Add unit tests for this. No, seriously.
# TODO: None of this handler is re-entrant - if you back up a few requests, it will
# behave strangely. Refactor it to fix this. Also, it won't work properly for multiple
# stats requests per page - it will mix them up.
# TODO: Permissions. Will want to cache these lookups!
class RouterStatsStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.USER, BaseWebsocketHandler.SUPER]

	def open(self):
		# Fetch our stats loader.
		self.stats_output = paasmaker.router.stats.ApplicationStats(
			self.configuration,
			self._on_stats_result,
			self._on_stats_error
		)
		self.last_message = None

	def on_message(self, message):
		# Message should be JSON.
		parsed = self.parse_message(message)
		if parsed:
			if parsed['request'] == 'update':
				self.handle_update(parsed)

	def handle_update(self, message):
		# Must match the request schema.
		request = self.validate_data(message, RouterStatsRequestSchema())
		if request:
			# Request some stats.
			# TODO: Check permissions!
			self.last_message = message
			self.stats_output.for_name(request['name'], int(request['input_id']))

	def _on_stats_result(self, result):
		# Send back the pretty tree to the client.
		self.send_success('update', result)

	def _on_stats_error(self, error, exception=None):
		self.send_error(error, self.last_message)

	def on_close(self):
		pass

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/router/stats/stream", RouterStatsStreamHandler, configuration))
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
		request = self.fetch_with_user_auth('http://localhost:%d/router/nginx?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertIn(str(self.configuration.get_flat('redis.table.port')), response.body)

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
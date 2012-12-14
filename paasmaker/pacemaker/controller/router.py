
import json
import time

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest, BaseWebsocketHandler
from paasmaker.common.core import constants

import tornado
import colander
from ws4py.client.tornadoclient import TornadoWebSocketClient

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

class RouterHistoryRequestSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Name of history requested",
		description="The name of the history requested (eg, workspace, application, etc)")
	input_id = colander.SchemaNode(colander.String(),
		title="The input ID",
		description="The input ID of the history requested (eg, workspace ID, application ID, etc)")
	metric = colander.SchemaNode(colander.String(),
		title="The metric to fetch",
		description="The metric to fetch the history for.")
	start = colander.SchemaNode(colander.Integer(),
		title="Start time",
		description="Start of the history period to request for - a unix timestamp.")
	end = colander.SchemaNode(colander.Integer(),
		title="End time",
		description="End of the history period to request for - a unix timestamp. Omit to select the latest time.",
		missing=None,
		default=None)

# TODO: Permissions. Will want to cache these lookups!
class RouterStatsStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.USER, BaseWebsocketHandler.SUPER]

	def open(self):
		# Fetch our stats loader.
		self.stats_output = paasmaker.router.stats.ApplicationStats(
			self.configuration
		)
		self.ready = False
		self.error = None
		self.stats_output.setup(
			self._on_stats_ready,
			self._on_stats_error
		)

	def _on_stats_ready(self):
		self.ready = True
		self.send_success('ready', True)

	def _on_stats_error(self, error, exception=None):
		self.ready = False
		self.error = error

	def on_message(self, message):
		# Message should be JSON.
		parsed = self.parse_message(message)
		if parsed:
			if self.error:
				self.send_error(self.error, parsed)
			elif not self.ready:
				self.send_error("Not yet ready. Sorry.", parsed)

			if parsed['request'] == 'update':
				self.handle_update(parsed)
			if parsed['request'] == 'history':
				self.handle_history(parsed)

	def handle_update(self, message):
		def got_stats(stats):
			self.send_success('update', stats)

		def failed_stats(error, exception=None):
			self.send_error('error', message)

		def got_set(vtset):
			self.stats_output.total_for_list(vtset, got_stats, failed_stats)

		# Must match the request schema.
		request = self.validate_data(message, RouterStatsRequestSchema())
		if request:
			# Request some stats.
			# TODO: Check permissions!
			self.stats_output.vtset_for_name(
				request['name'],
				int(request['input_id']),
				got_set
			)

	def handle_history(self, message):
		# Must match the request schema.
		request = self.validate_data(message, RouterHistoryRequestSchema())
		end = int(time.time())

		def got_history(history):
			self.send_success('history',
				{
					'points': history,
					'name': request['name'],
					'input_id': request['input_id'],
					'start': request['start'],
					'end': end
				}
			)

		def failed_history(error, exception=None):
			self.send_error('error', message)

		def got_set(vtset):
			self.stats_output.history_for_list(
				vtset,
				request['metric'],
				got_history,
				failed_history,
				request['start'],
				request['end']
			)

		if request:
			# Request some stats.
			# TODO: Check permissions!
			self.stats_output.vtset_for_name(
				request['name'],
				int(request['input_id']),
				got_set
			)

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

class RouterStreamHandlerTestClient(TornadoWebSocketClient):
	def opened(self):
		self.messages = []

	def closed(self, code, reason=None):
		#print "Client: closed"
		pass

	def update(self, name, input_id):
		data = {'name': name, 'input_id': input_id}
		auth = {'method': 'super', 'value': self.configuration.get_flat('pacemaker.super_token')}
		message = {'request': 'update', 'data': data, 'auth': auth}
		self.send(json.dumps(message))

	def history(self, name, input_id, metric, start, end=None):
		data = {'name': name, 'input_id': input_id, 'metric': metric, 'start': start, 'end': end}
		auth = {'method': 'super', 'value': self.configuration.get_flat('pacemaker.super_token')}
		message = {'request': 'history', 'data': data, 'auth': auth}
		self.send(json.dumps(message))

	def received_message(self, m):
		#print "Client: got %s" % m
		# Record the log lines.
		# CAUTION: m is NOT A STRING.
		parsed = json.loads(str(m))
		self.messages.append(parsed)

class RouterStreamHandlerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = RouterStatsStreamHandler.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_router_stream(self):
		client = RouterStreamHandlerTestClient("ws://localhost:%d/router/stats/stream" % self.get_http_port(), io_loop=self.io_loop)
		client.configuration = self.configuration
		client.connect()

		# Wait for it to announce it's ready.
		self.short_wait_hack(length=0.2)

		# Ask for updates.
		client.update('workspace', 1)
		client.update('version_type', 1)

		self.short_wait_hack()

		client.history('workspace', 1, 'requests', time.time() - 60)
		client.history('version_type', 1, 'requests', time.time() - 60)
		client.history('workspace', 1, 'requests', time.time() - 60, time.time())
		client.history('version_type', 1, 'requests', time.time() - 60, time.time())

		# Wait for it all to complete.
		self.short_wait_hack()

		#print json.dumps(client.messages, indent=4, sort_keys=True)

		# Now, analyze what happened.
		# TODO: Make this clearer and more exhaustive.
		expected_types = [
			'ready',
			'error',
			'update',
			'history',
			'history',
			'history',
			'history'
		]

		self.assertEquals(len(expected_types), len(client.messages), "Not the right number of messages.")
		for i in range(len(expected_types)):
			self.assertEquals(client.messages[i]['type'], expected_types[i], "Wrong type for message %d" % i)
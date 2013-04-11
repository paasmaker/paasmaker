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

class TableDumpController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		def on_dump_complete(table, serial, session):
			self.add_data('table', table)
			self.add_data('serial', serial)
			self.add_data('frontend_domain_postfix', self.configuration.get_flat('pacemaker.frontend_domain_postfix'))
			self.render("router/dump.html")
			session.close()

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

class StatsSnapshotController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self, name, input_id=None):
		# See if we have permissions.
		stats = paasmaker.router.stats.ApplicationStats(self.configuration)

		required_permissions = stats.permission_required_for(name, input_id, self.session)

		if not required_permissions[0]:
			# The input doesn't exist.
			raise tornado.web.HTTPError(404, "No stats to fetch for that input.")

		# Hard requirement on the permission.
		self.require_permission(required_permissions[1], required_permissions[2])

		def stats_read(values):
			values['as_at'] = time.time()
			self.add_data('values', values)

			stats.close()

			self.render("api/apionly.html")

		def stats_reader_ready():
			# Fetch those stats.
			stats.stats_for_name(name, input_id, stats_read)

		def stats_reader_error(message, exception=None):
			raise tornado.web.HTTPError(500, message)

		# Set up and fetch the stats.
		stats.setup(stats_reader_ready, stats_reader_error)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/router/stats/([a-z_]+)/([0-9]+)", StatsSnapshotController, configuration))
		routes.append((r"/router/stats/([a-z]+)", StatsSnapshotController, configuration))
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
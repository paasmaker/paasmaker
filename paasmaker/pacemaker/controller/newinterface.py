#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class NewInterfaceController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.render("new.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/new", NewInterfaceController, configuration))
		return routes

class NewInterfaceQUnitTestController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.render("qunit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/qunit", NewInterfaceQUnitTestController, configuration))
		return routes
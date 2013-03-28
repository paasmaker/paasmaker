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

class ToolsController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		self.render("tools.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/tools", ToolsController, configuration))
		return routes


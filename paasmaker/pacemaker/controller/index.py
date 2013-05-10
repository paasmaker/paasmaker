#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import json

import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado

class IndexController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		if self.configuration.is_pacemaker():
			if self.get_current_user():
				self.client_side_render()
			else:
				self.redirect("/login")
		else:
			self.render("index-notpacemaker.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", IndexController, configuration))
		return routes

# A controller for URLs that only ever exist on the front end.
class VirtualPageController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		# Administration homepage.
		routes.append((r"/administration/list", VirtualPageController, configuration))
		# Virtual "job" following pages for versions.
		routes.append((r"/version/\d+/[a-z]+/[-a-z0-9]+", VirtualPageController, configuration))
		routes.append((r"/workspace/\d+/applications/new/[-a-z0-9]+", VirtualPageController, configuration))
		routes.append((r"/application/\d+/newversion/[-a-z0-9]+", VirtualPageController, configuration))
		# Generic log viewers for versions or nodes.
		routes.append((r"/version/\d+/log/[-a-z0-9]+", VirtualPageController, configuration))
		routes.append((r"/node/\d+/log/[-a-z0-9]+", VirtualPageController, configuration))
		return routes
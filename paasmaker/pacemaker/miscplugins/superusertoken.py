#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

# This file contains a plugin that is used by integration tests,
# as a shortcut to get a user's API key via the super token
# authentication. This isn't possible in normal Paasmaker core,
# and is not for security reasons.

import paasmaker

from paasmaker.common.controller.base import BaseController

import colander
import tornado

class SuperUserTokenConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class SuperUserTokenMetadata(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.STARTUP_ROUTES: None,
	}
	OPTIONS_SCHEMA = SuperUserTokenConfigurationSchema()
	API_VERSION = "0.9.0"

	def add_routes(self, routes, route_extras):
		# Add the additional route required.
		routes.extend(SuperUserTokenController.get_routes(route_extras))

class SuperUserTokenController(BaseController):
	AUTH_METHODS = [BaseController.SUPER]

	def get(self, user_id):
		user = self.session.query(
			paasmaker.model.User
		).get(user_id)

		if user is None:
			raise tornado.web.HTTPError(404, "No such user.")

		self.add_data('apikey', user.apikey)
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/debug/userkey/(\d+)", SuperUserTokenController, configuration))
		return routes
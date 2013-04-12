#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import json
import email
import datetime
import os
import stat
import time

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from paasmaker.util import plugin

import tornado
import colander

class PluginResourceBaseController(BaseController):

	def _send_file(self, filename):
		# This code has been "borrowed" from Tornado's static file handler.
		stat_result = os.stat(filename)
		modified = datetime.datetime.fromtimestamp(stat_result[stat.ST_MTIME])

		self.set_header("Last-Modified", modified)

		# Check the If-Modified-Since, and don't send the result if the
		# content has not been modified
		ims_value = self.request.headers.get("If-Modified-Since")
		if ims_value is not None:
			date_tuple = email.utils.parsedate(ims_value)
			if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
			if if_since >= modified:
				self.set_status(304)
				self.finish()
				return

		with open(filename, "rb") as file:
			data = file.read()
			self.write(data)
			self.finish()

class PluginResourceJsController(PluginResourceBaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self, plugin_name, mode):
		if mode not in plugin.MODE.ALL:
			raise tornado.web.HTTPError(400, "No such plugin mode.")

		exists = self.configuration.plugins.exists(
			plugin_name,
			mode
		)

		if not exists:
			raise tornado.web.HTTPError(404, "No such plugin.")

		result = self.configuration.plugins.locate_resource_for(
			plugin_name,
			"%s.js" % mode
		)

		if result is None:
			raise tornado.web.HTTPError(404, "No such resource.")

		self.set_header("Content-Type", 'text/javascript')
		self._send_file(result)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/plugin/([-a-z0-9._]+)/([A-Z_]+)\.js", PluginResourceJsController, configuration))
		return routes

class PluginResourceCssController(PluginResourceBaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self, plugin_name):
		exists = self.configuration.plugins.exists_at_all(
			plugin_name
		)

		if not exists:
			raise tornado.web.HTTPError(404, "No such plugin.")

		result = self.configuration.plugins.locate_resource_for(
			plugin_name,
			"css"
		)

		if result is None:
			raise tornado.web.HTTPError(404, "No such resource.")

		self.set_header("Content-Type", 'text/css')
		self._send_file(result)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/plugin/([-a-z0-9._]+)/stylesheet.css$", PluginResourceCssController, configuration))
		return routes
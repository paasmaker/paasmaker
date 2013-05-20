#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import glob
import subprocess
import logging
import copy
import datetime

import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado

# To set up your environment:
# * Assuming you've used the example-paasmaker-hacking.yml installation file on your
#   local machine.
# $ nvm use v0.8.22
# $ npm install requirejs -g
# And you're good to go.
# The install script will set this up for you if you use it.

class DevelopmentJavascriptController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		javascript_path = os.path.normpath(os.path.dirname(__file__) + '/../../static/js/')
		target_path = os.path.join(javascript_path, 'main-built.js')

		should_rebuild = False
		target_stat = os.stat(target_path)
		target_mtime = target_stat.st_mtime

		# Figure out if anything has changed, and thus we need to rebuild the JavaScript.
		matches = []
		for root, dirnames, filenames in os.walk(javascript_path):
			for filename in filenames:
				if filename != 'main-built.js':
					this_stat = os.stat(os.path.join(root, filename))

					if this_stat.st_mtime > target_mtime:
						should_rebuild = True

		self.set_header('Content-Type', 'text/html')

		if should_rebuild:
			self.output_cache = ""
			self.output_cache += "<pre>"
			self.output_cache += "Rebuild at " + str(datetime.datetime.now())

			environment = copy.deepcopy(os.environ)
			environment['PATH'] = "%s:%s" % (os.path.expanduser('~/.nvm/v0.8.22/bin'), environment['PATH'])

			def chunk(data):
				self.output_cache += data

			def complete(code):
				self.output_cache += "</pre>"
				if code == 0:
					self.write(self.output_cache)
					self.finish()
				else:
					raise tornado.web.HTTPError(500, "Failed to compile. " + self.output_cache)

			process = paasmaker.util.popen.Popen(
				['r.js', '-o', 'build.js'],
				cwd=javascript_path,
				env=environment,
				on_stdout=chunk,
				on_stderr=chunk,
				on_exit=complete
			)
		else:
			self.write("No rebuild required at this time.")
			self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/development/rebuild-javascript.txt", DevelopmentJavascriptController, configuration))
		return routes

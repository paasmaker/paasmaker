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

import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado

# To set up your environment:
# * Assuming you've used the example-paasmaker-hacking.yml installation file on your
#   local machine.
# $ nvm use v0.8.22
# $ npm install handlebars -g
# And you're good to go.

class TemplatesController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		complete_cache_path = os.path.normpath(os.path.dirname(__file__) + '/../../static/js/')
		complete_cache_file = os.path.join(complete_cache_path, 'pm.templates.js')

		templates_path = os.path.normpath(os.path.dirname(__file__) + '/../../templates/')
		all_templates = glob.glob(os.path.join(templates_path, '*', '*.handlebars'))
		all_templates.sort()

		something_recompiled = False
		for source_path in all_templates:
			target_path = source_path + '.js'

			recompile = True
			if os.path.exists(target_path):
				# Compare the two.
				source_stat = os.stat(source_path)
				target_stat = os.stat(target_path)

				if source_stat.st_mtime < target_stat.st_mtime:
					recompile = False

			if recompile:
				logging.debug("Compiling template %s", source_path)
				# TODO: This assumes that you installed your dev copy with the example-paasmaker-hacking.yml
				# configuration file (without alterations).
				# We are assuming that you're using NVM and have v0.8.22 of Node installed via it,
				# and that you've installed handlebars.
				# TODO: Supply an error message when this isn't working.
				environment = copy.deepcopy(os.environ)
				environment['PATH'] = "%s:%s" % (os.path.expanduser('~/.nvm/v0.8.22/bin'), environment['PATH'])
				# This is currently done sync.
				# Also relies on having handlebars installed in the path.
				subprocess.check_call(['handlebars', source_path, '-f', target_path], env=environment)
				something_recompiled = True

		# Assemble them all into one file.
		if something_recompiled:
			logging.debug("Reassembling compiled templates file.")
			writer = open(complete_cache_file, 'w')
			for source_path in all_templates:
				writer.write(open(source_path + '.js', 'r').read())
			writer.close()
		else:
			logging.debug("No templates were updated, so no compilation done.")

		# And return that file now.
		self.set_header('Content-Type', 'text/javascript')
		self.write(open(complete_cache_file, 'r').read())
		self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/development/templates.js", TemplatesController, configuration))
		return routes

import logging
import os
import tempfile
import subprocess
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from ..scmlist.base import BaseSCMList

import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ScmListSchema(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String(),
		title="Plugin name",
		description="The plugin name to ask for a list.")
	bypass_cache = colander.SchemaNode(colander.Boolean(),
		title="Bypass the cache",
		description="Ask the SCM list plugin to bypass it's cached version, if present.",
		default=False,
		missing=False)

class ScmListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	@tornado.web.asynchronous
	def get(self):
		# TODO: Permissions... but against what?
		# Force JSON response.
		self._set_format('json')

		self.validate_data(ScmListSchema())

		plugin_exists = self.configuration.plugins.exists(
			self.params['plugin'],
			paasmaker.util.plugin.MODE.SCM_LIST
		)

		if not plugin_exists:
			self.add_error('No such listing plugin %s' % self.params['plugin'])
			self._render()
			return

		plugin = self.configuration.plugins.instantiate(
			self.params['plugin'],
			paasmaker.util.plugin.MODE.SCM_LIST,
			{},
			logger
		)

		plugin.get_repo_list(
			self.params['bypass_cache'],
			self._got_list,
			self._got_error
		)

	def _got_list(self, result):
		self.add_data('repositories', result)
		self._render()

	def _got_error(self, error, exception=None):
		logger.error(error)
		if exception:
			logger.error(exc_info=exception)
		self.add_error(error)
		self._render()

	def _render(self):
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/scm/list/repos", ScmListController, configuration))
		return routes

class DummySCMList(BaseSCMList):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_LIST: None
	}

	def get_repo_list(self, bypass_cache, callback, error_callback):
		callback([
			{
				'title': 'Test Entry 1',
				'url': 'http://repoprovider.com/path/to/repo'
			},
			{
				'title': 'Test Entry 2',
				'url': 'http://repoprovider.com/path/to/repo/2'
			}
		])

class DummySCMErrorList(BaseSCMList):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_LIST: None
	}

	def get_repo_list(self, bypass_cache, callback, error_callback):
		error_callback("Failed to fetch list.")

class ScmListControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ScmListController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		# Register the plugins.
		self.configuration.plugins.register(
			'paasmaker.scmlist.dummy',
			'paasmaker.pacemaker.controller.scmlist.DummySCMList',
			{},
			'Dummy SCM List'
		)
		self.configuration.plugins.register(
			'paasmaker.scmlist.dummyerror',
			'paasmaker.pacemaker.controller.scmlist.DummySCMErrorList',
			{},
			'Dummy SCM Error List'
		)

		# Now ask the controllers for the list.
		self.fetch_with_user_auth('http://localhost:%d/scm/list/repos?plugin=paasmaker.scmlist.dummy')
		response = self.wait()

		self.failIf(response.error)
		parsed = json.loads(response.body)
		self.assertEquals(len(parsed['data']['repositories']), 2, "Wrong number of repos returned.")

		# Try again with a specific error list.
		self.fetch_with_user_auth('http://localhost:%d/scm/list/repos?plugin=paasmaker.scmlist.dummyerror')
		response = self.wait()

		self.failIf(response.error)
		parsed = json.loads(response.body)
		self.assertEquals(len(parsed['errors']), 1, "Wrong number of errors returned.")
		self.assertIn("Failed to", parsed['errors'][0], "Wrong error returned.")

		# Try again with an invalid plugin.
		self.fetch_with_user_auth('http://localhost:%d/scm/list/repos?plugin=nope')
		response = self.wait()

		self.failIf(response.error)
		parsed = json.loads(response.body)
		self.assertEquals(len(parsed['errors']), 1, "Wrong number of errors returned.")
		self.assertIn("No such", parsed['errors'][0], "Wrong error returned.")
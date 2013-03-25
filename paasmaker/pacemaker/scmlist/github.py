
import json
import unittest

import paasmaker
from base import BaseSCMList, BaseSCMListTest

import tornado
import colander

# TODO: Make this more secure than storing the username/password
# in the clear in the configuration file!
# TODO: Implement a caching strategy.

class GitHubSCMListOptionsSchema(colander.MappingSchema):
	username = colander.SchemaNode(colander.String(),
		title="GitHub Username",
		description="The GitHub username to log in as.")
	password = colander.SchemaNode(colander.String(),
		title="GitHub Password",
		description="The GitHub password to use to login.")
	url_base = colander.SchemaNode(colander.String(),
		title="URL Base",
		description="The URL base for repositories, which governs how you access them. Prepended to the URL.",
		default="git@github.com:",
		missing="git@github.com:")
	url_postfix = colander.SchemaNode(colander.String(),
		title="URL Postfix",
		description="The postfix added to the URL.",
		default=".git",
		missing=".git")

class GitHubSCMList(BaseSCMList):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_LIST: None
	}
	OPTIONS_SCHEMA = GitHubSCMListOptionsSchema()
	API_VERSION = "0.9.0"

	def get_repo_list(self, bypass_cache, callback, error_callback):
		def got_list(response):
			if response.error:
				error_callback(str(response.error), exception=response.error)
			else:
				# Success! Parse the body.
				parsed = json.loads(response.body)
				result = self._parse_list(parsed)
				callback(result, "Successfully fetched list.")

		endpoint = "https://api.github.com/user/repos"

		request = tornado.httpclient.HTTPRequest(
			endpoint,
			auth_username=self.options['username'],
			auth_password=self.options['password']
		)
		client = tornado.httpclient.AsyncHTTPClient(
			io_loop=self.configuration.io_loop
		)
		client.fetch(request, got_list)

	def _parse_list(self, repolist):
		result = []
		for repo in repolist:
			result.append({'title': repo['name'], 'url': repo['ssh_url']})
		return result

class GitHubSCMListTest(BaseSCMListTest):

	@unittest.skip("Requires a username and password.")
	def test_list(self):
		# CAUTION: When testing, you will need to put in a username and
		# password below. Don't check this in for obvious reasons. If you
		# do check it in... well, I guess you'll be changing your password.
		self.registry.register(
			'paasmaker.scmlist.github',
			'paasmaker.pacemaker.scmlist.github.GitHubSCMList',
			{
				'username': 'XXXXXXXX',
				'password': 'XXXXXXXX'
			},
			'GitHub SCM list'
		)

		logger = self.configuration.get_job_logger('testscmlist')
		plugin = self.registry.instantiate(
			'paasmaker.scmlist.github',
			paasmaker.util.plugin.MODE.SCM_LIST,
			None,
			logger
		)

		plugin.get_repo_list(False, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Did not succeed.")
		self.assertTrue(len(self.repos) > 0, "Did not return any repos.")
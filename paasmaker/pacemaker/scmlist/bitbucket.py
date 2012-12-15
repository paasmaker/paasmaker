
import json
import unittest

import paasmaker
from base import BaseSCMList, BaseSCMListTest

import tornado
import colander

# TODO: Make this more secure than storing the username/password
# in the clear in the configuration file!
# TODO: Implement a caching strategy.

class BitbucketSCMListOptionsSchema(colander.MappingSchema):
	username = colander.SchemaNode(colander.String(),
		title="Bitbucket Username",
		description="The BitBucket username to log in as.")
	password = colander.SchemaNode(colander.String(),
		title="Bitbucket Password",
		description="The BitBucket password to use to login.")
	url_base = colander.SchemaNode(colander.String(),
		title="URL Base",
		description="The URL base for repositories, which governs how you access them. Prepended to the URL.",
		default="git@bitbucket.org:",
		missing="git@bitbucket.org:")

class BitbucketSCMList(BaseSCMList):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_LIST: None
	}
	OPTIONS_SCHEMA = BitbucketSCMListOptionsSchema()

	def get_repo_list(self, callback, error_callback):
		def got_list(response):
			if response.error:
				error_callback(str(response.error))
			else:
				# Success! Parse the body.
				parsed = json.loads(response.body)
				result = self._parse_list(parsed)
				callback(result, "Successfully fetched list.")

		endpoint = "https://api.bitbucket.org/1.0/user/repositories/"

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
			title = "%(slug)s" % repo
			url = self.options['url_base'] + "%(owner)s/%(slug)s" % repo
			result.append({'title': title, 'url': url})
		return result

class BitbucketSCMListTest(BaseSCMListTest):

	@unittest.skip("Requires a username and password.")
	def test_list(self):
		# CAUTION: When testing, you will need to put in a username and
		# password below. Don't check this in for obvious reasons. If you
		# do check it in... well, I guess you'll be changing your password.
		self.registry.register(
			'paasmaker.scmlist.bitbucket',
			'paasmaker.pacemaker.scmlist.bitbucket.BitbucketSCMList',
			{
				'username': 'XXXXXXXX',
				'password': 'XXXXXXXX'
			},
			'BitBucket SCM list'
		)

		logger = self.configuration.get_job_logger('testscmlist')
		plugin = self.registry.instantiate(
			'paasmaker.scmlist.bitbucket',
			paasmaker.util.plugin.MODE.SCM_LIST,
			None,
			logger
		)

		plugin.get_repo_list(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Did not succeed.")
		self.assertTrue(len(self.repos) > 0, "Did not return any repos.")

import uuid
import os
import re

import paasmaker

import tornado
import tornado.testing
import colander

class BaseSCMListConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseSCMListParametersSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseSCMList(paasmaker.util.plugin.Plugin):
	"""
	SCM list plugins are meant to fetch a list of repositories of
	a particular type, to be able to display a drop down list in
	the web interface for convenience.

	For example, the first plugin shipped is one for BitBucket.
	This provides a list of BitBucket repositories available to
	the credentials supplied.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.SCM_LIST: None
	}

	# These are defaults - you should set your own.
	OPTIONS_SCHEMA = BaseSCMListConfigurationSchema()

	def get_repo_list(self, bypass_cache, callback, error_callback):
		"""
		Return a list of URLs and titles for this SCM.
		The returned list should look like so::

			[
				{
					'title': 'Title',
					'url': 'url_to_repo'
				}
			]

		:arg bool bypass_cache: If True, don't use a cached version
			of the list.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The error callback to call if something
			goes wrong.
		"""
		raise NotImplementedError("You must implement get_url_list().")

class BaseSCMListTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseSCMListTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.repos = None
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseSCMListTest, self).tearDown()

	def success_callback(self, repos, message):
		self.success = True
		self.message = message
		self.repos = repos
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.repos = None
		self.stop()
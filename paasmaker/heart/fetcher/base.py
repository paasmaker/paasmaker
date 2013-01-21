
import time
import os

import tornado.testing
import paasmaker

import colander

class BaseFetcherConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseFetcher(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.FETCHER: None
	}
	OPTIONS_SCHEMA = BaseFetcherConfigurationSchema()

	def fetch(self, url, remote_filename, target_filename, callback, error_callback):
		"""
		Fetch the given URL to this node, using whatever method is
		appropriate. You should write the result to the target filename
		supplied. The plugin might not be called if the local file
		already exists, as it probably won't have to be fetched again.

		You should log periodicaly, to self.logger, to update on
		the progress of any download if you're having to download
		files. This won't always make sense or be possible.

		Once done, call the callback with a message.
		"""
		raise NotImplementedError("You must implement fetch().")

class BaseFetcherTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseFetcherTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.success = None
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseFetcherTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()
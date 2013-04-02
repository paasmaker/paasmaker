#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import time
import os

import tornado.testing
import paasmaker

import colander

class BaseFetcherConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseFetcher(paasmaker.util.plugin.Plugin):
	"""
	These plugins are used to fetch the prepared applications
	from a remote server, onto the local node for execution.

	The default plugin, paasmakernode, just fetches the prepared
	package from the master node. In the future, we hope to be
	able to supply plugins that can fetch packages from Amazon S3,
	or other scalable redundant storage.
	"""
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
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
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
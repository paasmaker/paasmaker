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

class BaseUnpackerConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseUnpacker(paasmaker.util.plugin.Plugin):
	"""
	These plugins are able to take a downloaded package file,
	and unpack them into the appropriate location, ready for
	execution.

	At the moment, the default unpacker, the tarball unpacker,
	just unpacks the tarball, as the name might suggest. The other
	unpacker is the development directory unpacker, which symlinks
	the development location to the instance root.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.UNPACKER: None
	}
	OPTIONS_SCHEMA = BaseUnpackerConfigurationSchema()

	def unpack(self, package_path, target_path, original_url, callback, error_callback):
		"""
		Unpack the given package path into the supplied target path.
		Call the callback once complete with a message.

		:arg str package_path: The path to the package.
		:arg str target_path: The path that it should be unpacked to.
		:arg str original_url: The full original URL of the package. Not normally
			needed.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The callback to call when an
			error occurs.
		"""
		raise NotImplementedError("You must implement unpack().")

class BaseUnpackerTest(tornado.testing.AsyncTestCase, paasmaker.common.testhelpers.TestHelpers):
	def setUp(self):
		super(BaseUnpackerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.success = None
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseUnpackerTest, self).tearDown()

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
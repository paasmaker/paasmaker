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

class BaseStorerConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseStorer(paasmaker.util.plugin.Plugin):
	"""
	These plugins are designed to take packed prepared applications,
	and place them into storage in a location where the heart nodes
	can fetch them later. These plugins emit a URL which describes
	where the file is stored. The default plugin emits a URL like
	``paasmaker:://<node UUID>/filename``, which indicates which
	Paasmaker node to contact to fetch the package.

	In future, it is hoped to have other storage methods, like a plugin
	that can upload a packed application to S3, to improve redundancy
	and scale up to larger clusters.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.STORER: None
	}
	OPTIONS_SCHEMA = BaseStorerConfigurationSchema()

	def store(self, package_file, package_checksum, package_type, callback, error_callback):
		"""
		Store the supplied package file somewhere. The supplied package_file
		is ready to go. If you upload it to a remote location, you might like
		to delete the local copy once you are sure it exists remotely.

		Call the callback with a URI that can be used to fetch the file
		later. For example, the local storer emits a url like so::

			paasmaker://<node UUID>/<packed_filename>

		But a plugin that stores the files on S3 might emit a URL like so::

			s3://<bucket>/<path>

		The scheme of the URL is used to determine what plugin fetches that
		package. The idea is that you don't need to put secret credentials into
		the URL, and instead configure the plugin on each node with the credentials
		that it needs to fetch the package.

		Call the callback with the URL to the resource.

		:arg str package_file: The full path to the local package file.
		:arg str package_checksum: The checksum of the package file.
		:arg str package_type: A string describing the type of package. This
			is the type given by the packer plugin.
		:arg callable callback: The callback to call when done.
		:arg callable error_callback: The error callback to call when something
			goes wrong.
		"""
		raise NotImplementedError("You must implement store().")

class BaseStorerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseStorerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.url = None
		self.success = None
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(BaseStorerTest, self).tearDown()

	def success_callback(self, url, message):
		self.success = True
		self.url = url
		self.message = message
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.url = None
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()
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

class BasePackerConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BasePacker(paasmaker.util.plugin.Plugin):
	"""
	These plugins are responsible for packing up prepared applications
	into a file that can be stored somewhere. The only function here
	is to take a directory and output a packed file.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.PACKER: None
	}
	OPTIONS_SCHEMA = BasePackerConfigurationSchema()

	def pack(self, directory, pack_name_prefix, callback, error_callback):
		"""
		Pack the files in the given directory into the appropriate format.
		Call the callback as so::

			callback(pack_type, pack_file, checksum, message)

		The supplied directory is a temporary directory with a few exceptions.
		You should remove this directory once you've packed up the code.
		The ``BasePacker`` provides a helper function to do this for you.
		(The exception to this rule is for the dev directory plugin,
		in which case you won't want to remove it because it's a developers
		direct source directory. The helper function, ``_remove_temporary_directory``
		has protections to prevent it from removing directories outside of the
		scratch directory to assist with this).

		:arg str directory: The directory containing the prepared source code.
		:arg str pack_name_prefix: The path to where you should store the file,
			and the starting filename. You should add an appropriate extension
			to the file, and then emit that name via the callback.
		:arg callable callback: The callback to call upon success.
		:arg callable error_callback: The callback to call upon error.
		"""
		raise NotImplementedError("You must implement pack().")

	def _remove_temporary_directory(self, directory, callback):
		# Helper function to remove a temporary directory.
		cleanup_log_fp = self.logger.takeover_file()
		cleanup_command = ['rm', '-rfv', directory]

		# Safeguard: make sure that the directory is a sub path
		# of the scratch directory.
		absdir = os.path.abspath(directory)
		scratch = self.configuration.get_flat('scratch_directory')

		if not absdir.startswith(scratch):
			raise ValueError("Supplied directory is not a child of the scratch directory. For safety, we're refusing to remove it.")

		def cleanup_complete(code):
			self.logger.untakeover_file(cleanup_log_fp)
			self.logger.info("Finished removing temporary directory. Code %d.", code)
			callback(code)

		cleanup_runner = paasmaker.util.Popen(cleanup_command,
			stdout=cleanup_log_fp,
			stderr=cleanup_log_fp,
			on_exit=cleanup_complete,
			cwd=directory,
			io_loop=self.configuration.io_loop)

	def _calculate_checksum(self, packed_file, callback):
		# Helper function to calculate a checksum.
		calc = paasmaker.util.streamingchecksum.StreamingChecksum(
			packed_file,
			self.configuration.io_loop,
			self.logger
		)
		calc.start(callback)

class BasePackerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePackerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.pack_type = None
		self.pack_file = None
		self.checksum = None
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(BasePackerTest, self).tearDown()

	def success_callback(self, pack_type, pack_file, checksum, message):
		self.success = True
		self.pack_type = pack_type
		self.pack_file = pack_file
		self.checksum = checksum
		self.message = message
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.pack_file = None
		self.pack_type = None
		self.checksum = None
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()
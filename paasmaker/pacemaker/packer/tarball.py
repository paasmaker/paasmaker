#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import shutil

from base import BasePacker, BasePackerTest
import paasmaker

import colander

class TarballPacker(BasePacker):
	API_VERSION = "0.9.0"

	def pack(self, directory, pack_name_prefix, callback, error_callback):
		# Generate the full name for the package.
		package_full_name = "%s.tar.gz" % pack_name_prefix

		self.logger.debug("Packing code into a tarball.")

		# Fire off the pack command.
		pack_command = ['tar', 'zcvf', package_full_name, '.']

		self.log_fp = self.logger.takeover_file()

		def pack_complete(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command result: %d" % code)
			if code == 0:
				self.logger.info("Successfully packed source code.")
			else:
				self.logger.error("Unable to pack up source code.")

			# Regardless of success, delete the temporary directory.
			# And then emit the details based on the success or failure.
			def cleanup_complete(cleanup_code):
				self.logger.info("Finished removing temporary directory. Code %d.", cleanup_code)

				def checksum_complete(checksum):
					if code == 0:
						# And we're done.
						callback(
							'tarball',
							package_full_name,
							checksum,
							'Successfully packed source code.'
						)
					else:
						error_callback("Failed to pack source code.")

					# end of checksum_complete()

				# Now calculate the checksum.
				self._calculate_checksum(package_full_name, checksum_complete)

				# end of cleanup_complete()

			self.logger.info("Removing temporary directory...")
			self._remove_temporary_directory(directory, cleanup_complete)
			# end of pack_complete()

		packer_runner = paasmaker.util.Popen(pack_command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=pack_complete,
			cwd=directory,
			io_loop=self.configuration.io_loop)

class TarballPackerTest(BasePackerTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('testpacker')

		self.registry.register(
			'paasmaker.packer.tarball',
			'paasmaker.pacemaker.packer.tarball.TarballPacker',
			{},
			'Tarball Source Packer'
		)

		packer = self.registry.instantiate(
			'paasmaker.packer.tarball',
			paasmaker.util.plugin.MODE.PACKER,
			{},
			logger
		)

		# Create a new temp directory under the scratch dir to
		# pack up.

		# TODO: Move this code into the BasePackerTest class,
		# to save each packer plugin duplicating this code.
		test_code_original = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')
		test_source_path = self.configuration.get_scratch_path('paasmaker.packer.tarball.test')
		shutil.copytree(test_code_original, test_source_path)

		output_prefix = os.path.join(
			self.configuration.get_scratch_path_exists('packed'),
			"1_1"
		)

		packer.pack(test_source_path, output_prefix, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Should have succeeded")
		self.assertEquals(self.pack_type, "tarball", "Wrong pack type emitted.")
		self.assertEquals(self.pack_file, "%s.tar.gz" % output_prefix, "Wrong output filename.")
		self.assertTrue(os.path.exists(self.pack_file), "Reported pack file does not exist.")

		# TODO: Check that the checsum is correct?
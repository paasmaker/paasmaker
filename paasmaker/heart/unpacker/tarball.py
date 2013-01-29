
import os
import shutil

from base import BaseUnpacker, BaseUnpackerTest
import paasmaker

import colander

class TarballUnpacker(BaseUnpacker):

	def unpack(self, package_path, target_path, original_url, callback, error_callback):
		command = ['tar', 'zxvf', package_path]
		self.log_fp = self.logger.takeover_file()

		def command_complete(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("tar command returned code: %d", code)
			#self.configuration.debug_cat_job_log(logger.job_id)
			if code == 0:
				callback("Successfully unpacked files.")
			else:
				error_callback("Unable to extract files - return code %d." % code)

		extractor = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=command_complete,
			io_loop=self.configuration.io_loop,
			cwd=target_path)

class TarballUnpackerTest(BaseUnpackerTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('testunpacker')

		# Create a sample tar gz file.
		packed = self.pack_sample_application('tornado-simple')

		self.registry.register(
			'paasmaker.unpacker.tarball',
			'paasmaker.heart.unpacker.tarball.TarballUnpacker',
			{},
			'Tarball Source Unpacker'
		)

		unpacker = self.registry.instantiate(
			'paasmaker.unpacker.tarball',
			paasmaker.util.plugin.MODE.UNPACKER,
			{},
			logger
		)

		unpack_target = self.configuration.get_scratch_path_exists('paasmaker.unpacker.tarball.test')
		unpacker.unpack(
			packed,
			unpack_target,
			'dummy://url/', # This unpacker doesn't make use of this.
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "Did not succeed.")
		self.assertTrue(os.path.exists(os.path.join(unpack_target, 'app.py')), "Test file did not exist.")
		self.assertTrue(os.path.exists(os.path.join(unpack_target, 'manifest.yml')), "Test file did not exist.")

import os
import tempfile
import shutil
import subprocess

from base import BaseSCM, BaseSCMTest
import paasmaker

class TarballSCM(BaseSCM):
	def create_working_copy(self, callback, error_callback):
		# Make a directory to extract to.
		path = self.get_temporary_scm_dir()

		self.logger.info("Unpacking to %s", path)
		self.logger.info("Source tarball file %s", self.parameters['location'])

		compression_flag = ''
		if self.parameters['location'].endswith('.bz2'):
			compression_flag = 'j'
		if self.parameters['location'].endswith('.gz'):
			compression_flag = 'z'
		if self.parameters['location'].endswith('.tgz'):
			compression_flag = 'z'

		# Extract the supplied file to it.
		command = ['tar', 'xvf' + compression_flag, self.parameters['location']]

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		log_fp = self.logger.takeover_file()

		def cb(code):
			self.logger.untakeover_file(log_fp)
			self.logger.info("tar command returned code: %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				callback(path, "Successfully extracted files.")
			else:
				error_callback("Unable to extract files.")

		# Start the extractor. This will call cb() defined above when done.
		# TODO: Assumes that files inside the tarball are at the root level.
		extractor = paasmaker.util.Popen(command,
			stdout=log_fp,
			stderr=log_fp,
			on_exit=cb,
			io_loop=self.configuration.io_loop,
			cwd=path)

	def extract_manifest(self, manifest_path, callback, error_callback):
		self.logger.info("Extracting manifest file from %s", self.parameters['location'])

		# Create a temp dir to extract this to.
		temp_extract_path = tempfile.mkdtemp()

		compression_flag = ''
		if self.parameters['location'].endswith('.bz2'):
			compression_flag = 'j'
		if self.parameters['location'].endswith('.gz'):
			compression_flag = 'z'
		if self.parameters['location'].endswith('.tgz'):
			compression_flag = 'z'

		# Extract the supplied file to it.
		# TODO: './' on the front of the manifest path is a hack, and depends
		# on how the tarball was created in the first place.
		command = ['tar', 'xvf' + compression_flag, self.parameters['location'], './' + manifest_path]

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		log_fp = self.logger.takeover_file()

		def cb(code):
			self.logger.untakeover_file(log_fp)
			self.logger.info("Tar command returned code: %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				manifest_fp = open(os.path.join(temp_extract_path, manifest_path), 'r')
				manifest = manifest_fp.read()
				manifest_fp.close()

				shutil.rmtree(temp_extract_path)

				callback(manifest)
			else:
				# TODO: Make this error message more helpful.
				shutil.rmtree(temp_extract_path)
				error_callback("Unable to extract manifest.")

		# Start the extractor. This will call cb() defined above when done.
		extractor = paasmaker.util.Popen(command,
			stdout=log_fp,
			stderr=log_fp,
			on_exit=cb,
			io_loop=self.configuration.io_loop,
			cwd=temp_extract_path)

	def create_form(self):
		return """
		<div class="file-uploader-widget"></div>
		"""

	def create_summary(self):
		return {
			'location': 'The location of the tarball file. This can be an uploaded file.'
		}

class TarballSCMTest(BaseSCMTest):
	def test_simple(self):
		# Create a tarball file for us to use.
		# Cleanup will destroy this folder for us.
		temptarball = os.path.join(self.configuration.get_flat('scratch_directory'), 'tarballscmtest.tar.gz')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'tarballscmtest.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')
		command = ['tar', 'zcvf', temptarball, '.']

		tarrer = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary tarball file.")

		# Now unpack it using the plugin.
		logger = self.configuration.get_job_logger('testscmtarball')
		logger = self.configuration.get_job_logger('testscmzip')
		self.registry.register(
			'paasmaker.scm.tarball',
			'paasmaker.pacemaker.scm.tarball.TarballSCM',
			{},
			'Tarball SCM'
		)
		plugin = self.registry.instantiate(
			'paasmaker.scm.tarball',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{'location': temptarball},
			logger
		)

		# Extract a manifest file.
		plugin.extract_manifest('manifest.yml', self.stop, self.stop)
		result = self.wait()

		# Check that the manifest was returned.
		self.assertIn("format: 1", result, "Missing manifest contents.")

		# Try to extract an invalid manifest path.
		plugin.extract_manifest('manifest_noexist.yml', self.stop, self.stop)
		result = self.wait()
		self.assertIn("Unable to extract", result, "Missing error message.")

		# Proceed.
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not unpack properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'manifest.yml')), "manifest.yml does not exist.")

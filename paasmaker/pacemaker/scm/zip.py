
import os
import tempfile
import shutil

from base import BaseSCM, BaseSCMTest
import paasmaker

class ZipSCM(BaseSCM):
	MODES = [paasmaker.util.plugin.MODE.SCM_EXPORT, paasmaker.util.plugin.MODE.SCM_CHOOSER]

	def create_working_copy(self, callback, error_callback):
		# Make a directory to extract to.
		path = self.get_temporary_scm_dir()

		self.logger.info("Unpacking to %s", path)
		self.logger.info("Source zip file %s", self.parameters['location'])

		# Extract the supplied file to it.
		command = ['unzip', '-d', path, self.parameters['location']]

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		log_fp = self.logger.takeover_file()

		def cb(code):
			self.logger.untakeover_file(log_fp)
			self.logger.info("Zip command returned code: %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				callback(path, "Successfully extracted files.")
			else:
				error_callback("Unable to extract files.")

		# Start the extractor. This will call cb() defined above when done.
		extractor = paasmaker.util.Popen(command,
			stdout=log_fp,
			stderr=log_fp,
			on_exit=cb,
			io_loop=self.configuration.io_loop)

	def extract_manifest(self, manifest_path, callback, error_callback):
		self.logger.info("Extracting manifest file from %s", self.parameters['location'])

		# Create a temp dir to extract this to.
		temp_extract_path = tempfile.mkdtemp()

		# Extract the supplied file to it.
		command = ['unzip', '-d', temp_extract_path, self.parameters['location'], manifest_path]

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		log_fp = self.logger.takeover_file()

		def cb(code):
			self.logger.untakeover_file(log_fp)
			self.logger.info("Zip command returned code: %d", code)
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
			io_loop=self.configuration.io_loop)

	def create_form(self):
		return """
		<div class="file-uploader-widget"></div>
		"""

	def create_summary(self):
		return {
			'location': 'The location of the zip file. This can be an uploaded file.'
		}

class ZipSCMTest(BaseSCMTest):
	def test_simple(self):
		# Create a zip file for us to use.
		# Cleanup will destroy this folder for us.
		tempzip = os.path.join(self.configuration.get_flat('scratch_directory'), 'zipscmtest.zip')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'zipscmtest.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')
		command = ['zip', tempzip, 'app.py', 'manifest.yml']

		zipper = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary zip file.")

		# Now unpack it using the plugin.
		logger = self.configuration.get_job_logger('testscmzip')
		self.registry.register(
			'paasmaker.scm.zip',
			'paasmaker.pacemaker.scm.zip.ZipSCM',
			{},
			'Zip File SCM'
		)
		plugin = self.registry.instantiate(
			'paasmaker.scm.zip',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{'location': tempzip},
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

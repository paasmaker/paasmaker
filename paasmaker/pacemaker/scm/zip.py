
import os

from base import BaseSCM, BaseSCMTest
import paasmaker

class ZipSCM(BaseSCM):

	def create_working_copy(self, callback, error_callback):
		# Make a directory to extract to.
		path = self.get_temporary_scm_dir()

		self.logger.info("Unpacking to %s", path)
		self.logger.info("Source zip file %s", self.raw_parameters['location'])

		# Extract the supplied file to it.
		command = ['unzip', '-d', path, self.raw_parameters['location']]

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		log_fp = self.logger.takeover_file()

		def cb(code):
			self.logger.untakeover_file(log_fp)
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
		plugin = ZipSCM(self.configuration, {}, {'location': tempzip}, logger=logger)
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not unpack properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
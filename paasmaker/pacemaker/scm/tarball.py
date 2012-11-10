
import os

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
			{}
		)
		plugin = self.registry.instantiate(
			'paasmaker.scm.tarball',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{'location': temptarball},
			logger
		)

		# Proceed.
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not unpack properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")

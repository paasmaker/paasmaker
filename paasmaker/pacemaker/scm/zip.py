#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import tempfile
import shutil

from base import BaseSCM, BaseSCMTest
import paasmaker

class ZipSCM(BaseSCM):
	API_VERSION = "0.9.0"

	def create_working_copy(self, callback, error_callback):
		# Make a directory to extract to.
		path = self._get_temporary_scm_dir()

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
				# Mask the original filename that was uploaded with the parameters returned.
				callback(path, "Successfully extracted files.", {'location': 'uploaded file'})
			else:
				error_callback("Unable to extract files.")

		# Start the extractor. This will call cb() defined above when done.
		self.extractor = paasmaker.util.Popen(
			command,
			stdout=log_fp,
			stderr=log_fp,
			on_exit=cb,
			io_loop=self.configuration.io_loop
		)

	def _abort(self):
		self.extractor.kill()

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

		# Proceed.
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not unpack properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")

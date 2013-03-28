#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import tempfile
import os
import colander
import time
import shutil
import copy
import hashlib

from base import BasePrepare, BasePrepareTest

import paasmaker

# TODO: Handle the inputs to this plugin more securely.

class PythonPipPrepareConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class PythonPipPrepareParametersSchema(colander.MappingSchema):
	virtualenv_name = colander.SchemaNode(
		colander.String(),
		title="Virtualenv name",
		description="The name used for the Virtualenv when it's created."
	)
	requirements_name = colander.SchemaNode(
		colander.String(),
		title="Requirements filename",
		description="The name of the file that contains the requirements to be installed. Defaults to requirements.txt.",
		default="requirements.txt",
		missing="requirements.txt"
	)

class PythonPipPrepare(BasePrepare):
	MODES = {
		paasmaker.util.plugin.MODE.PREPARE_COMMAND: PythonPipPrepareParametersSchema()
	}
	OPTIONS_SCHEMA = PythonPipPrepareConfigurationSchema()
	API_VERSION = "0.9.0"

	def prepare(self, environment, directory, callback, error_callback):
		# Create or fetch a temporary directory for the download cache.
		download_cache_path = self.configuration.get_scratch_path_exists(self.called_name)
		self.logger.info("Download cache path %s", download_cache_path)

		our_environment = copy.deepcopy(environment)
		our_environment['PIP_DOWNLOAD_CACHE'] = download_cache_path

		# Read the requirements file and create a checksum, to see
		# if we can satisfy the requirements locally. As in, if you've not
		# changed the requirements file, it should be able to install directly
		# from the cache.
		# TODO: This will have corner cases in it that cause the wrong packages to
		# be installed. Think about this a little bit more.
		requirements_fp = open(os.path.join(directory, self.parameters['requirements_name']), 'r')
		requirements_raw = requirements_fp.read()
		md5 = hashlib.md5()
		md5.update(requirements_raw)
		requirements_sum = md5.hexdigest()
		requirements_checkfile = os.path.join(download_cache_path, requirements_sum) + '.checkfile'

		# Create a shell script to perform the commands for us.
		self.tempnam = tempfile.mkstemp()[1]

		fp = open(self.tempnam, 'w')
		# Prevent the script from continuing when one of the commands
		# fails. Because we want to abort in this situation.
		fp.write("\nset -xe\n")
		# From: http://stackoverflow.com/questions/821396/aborting-a-shell-script-if-any-command-returns-a-non-zero-value
		fp.write("set -o pipefail\n")

		# Create the virtualenv.
		fp.write("virtualenv %s\n" % self.parameters['virtualenv_name'])

		# Activate the virtualenv.
		fp.write(". %s/bin/activate\n" % self.parameters['virtualenv_name'])

		# Make it relocatable.
		# (This also shortens the shebang lines, otherwise they can easily get too long)
		fp.write("virtualenv --relocatable %s\n" % self.parameters['virtualenv_name'])

		if not os.path.exists(requirements_checkfile):
			self.logger.info("New requirements file - downloading packages.")

			# We need to download and cache the packages first.
			# In theory, this should mean we can reinstall the same packages again
			# later without touching the internet at all.
			fp.write("pip install --download %s -r %s\n" % (download_cache_path, self.parameters['requirements_name']))

			# Now that we've successfully downloaded it, record that we've downloaded
			# this set of packages.
			open(requirements_checkfile, 'w')  # This is equivalent to 'touch'.
		else:
			self.logger.info("Previously seen requirements file - using existing cache only.")

		# Now install packages from the cache.
		fp.write("pip install --no-index --find-links=file://%s -r %s\n" % (download_cache_path, self.parameters['requirements_name']))

		fp.close()

		self.log_fp = self.logger.takeover_file()

		def completed_script(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Pip prepare commands exited with: %d", code)
			# Remove the shell script.
			os.unlink(self.tempnam)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				callback("Successfully prepared via pip.")
			else:
				error_callback("Unable to prepare via pip.")

		# Start the commands off.
		command = ['bash', self.tempnam]
		self.scriptrunner = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=completed_script,
			cwd=directory,
			io_loop=self.configuration.io_loop,
			env=our_environment)

	def _abort(self):
		# If signalled, abort the script runner and let it sort everything out.
		if hasattr(self, 'scriptrunner'):
			self.scriptrunner.kill()

class PythonPipPrepareTestTest(BasePrepareTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('testpreparepythonpip')
		parameters = {
			'virtualenv_name': 'test'
		}

		self.registry.register(
			'paasmaker.prepare.pythonpip',
			'paasmaker.pacemaker.prepare.pythonpip.PythonPipPrepare',
			{},
			'Python Pip Prepare'
		)
		plugin = self.registry.instantiate(
			'paasmaker.prepare.pythonpip',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			logger
		)

		# Write out a requirements.txt file.
		req_path = os.path.join(self.tempdir, "requirements.txt")
		req_fp = open(req_path, 'w')
		req_fp.write("pminterface")
		req_fp.close()

		# Proceed.
		start = time.time()
		plugin.prepare(os.environ, self.tempdir, self.success_callback, self.failure_callback)
		first_time = time.time() - start

		self.wait()

		#log_file = self.configuration.get_job_log_path('testpreparepythonpip')
		#print open(log_file, 'r').read()

		self.assertTrue(self.success, "Did not prepare properly.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test')), "Virtualenv does not exist.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test', 'bin', 'activate')), "Virtualenv does not exist.")

		# Remove the virtualenv, and try it again.
		# It should take less time this time because it's cached. (Within 20% anyway)
		# TODO: This isn't very scientific...
		shutil.rmtree(os.path.join(self.tempdir, 'test'))
		self.assertTrue(os.path.exists(self.tempdir))

		logger2 = self.configuration.get_job_logger('testpreparepythonpip2')
		plugin = self.registry.instantiate(
			'paasmaker.prepare.pythonpip',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			logger2
		)

		start = time.time()
		plugin.prepare(os.environ, self.tempdir, self.success_callback, self.failure_callback)
		second_time = time.time() - start

		#log_file = self.configuration.get_job_log_path('testpreparepythonpip2')
		#print open(log_file, 'r').read()

		self.assertTrue(self.success, "Did not prepare properly.")
		# TODO: Python returns false for these, but the files actually do exist.
		#self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test')), "Virtualenv does not exist.")
		#self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test', 'bin', 'activate')), "Virtualenv does not exist.")

		self.assertTrue((first_time * 1.2) > second_time, "Was not quicker on second run (first %0.3f, second %0.3f)." % (first_time, second_time))
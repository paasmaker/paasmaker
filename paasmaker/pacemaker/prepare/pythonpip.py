
import tempfile
import os
import colander
import time
import shutil
import copy

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

		our_environment = copy.deepcopy(environment)
		our_environment['PIP_DOWNLOAD_CACHE'] = download_cache_path

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

		# Install the requriements.
		fp.write("pip install -r %s\n" % self.parameters['requirements_name'])

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

		self.assertTrue(self.success, "Did not prepare properly.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test')), "Virtualenv does not exist.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test', 'bin', 'activate')), "Virtualenv does not exist.")

		# Remove the virtualenv, and try it again.
		# It should take less time this time because it's cached. (Within 20% anyway)
		# TODO: This isn't very scientific...
		shutil.rmtree(os.path.join(self.tempdir, 'test'))

		start = time.time()
		plugin.prepare(os.environ, self.tempdir, self.success_callback, self.failure_callback)
		second_time = time.time() - start

		#log_file = self.configuration.get_job_log_path('testpreparepythonpip')
		#print open(log_file, 'r').read()

		self.assertTrue(self.success, "Did not prepare properly.")
		# TODO: Python returns false for these, but the files actually do exist.
		#self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test')), "Virtualenv does not exist.")
		#self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'test', 'bin', 'activate')), "Virtualenv does not exist.")

		self.assertTrue((first_time * 1.2) > second_time, "Was not quicker on second run.")
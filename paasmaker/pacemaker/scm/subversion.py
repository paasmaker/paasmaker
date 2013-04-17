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
import subprocess

import paasmaker
from base import BaseSCM, BaseSCMTest

import colander

# TODO: Authentication.

class SubversionSCMParametersSchema(colander.MappingSchema):
	location = colander.SchemaNode(colander.String(),
		title="Location of source",
		description="The URL to the repository.")
	revision = colander.SchemaNode(colander.String(),
		title="The revision to use",
		description="The Subversion revision to use. Defaults to HEAD.",
		missing="HEAD",
		default="HEAD")

class SubversionSCM(BaseSCM):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_EXPORT: SubversionSCMParametersSchema(),
		paasmaker.util.plugin.MODE.SCM_FORM: None
	}
	API_VERSION = "0.9.0"

	def create_working_copy(self, callback, error_callback):
		self.subversion_in_progress = False
		self.output_in_progress = False

		# Make a directory to extract to. It should be persistent.
		self.path = self._get_persistent_scm_dir()
		self.callback = callback
		self.error_callback = error_callback

		self.logger.info("Working directory: %s", self.path)
		self.logger.info("Source Subversion repo is %s", self.parameters['location'])

		self.subversion_worker = SubversionGetDirectoryUpToDate(
			self.configuration,
			self.path,
			self.parameters,
			self.logger
		)

		def subversion_up_to_date(path):
			# Move on to creating the output directory.
			self.subversion_in_progress = False
			self._create_output_directory()

		self.subversion_in_progress = True
		self.subversion_worker.start(subversion_up_to_date, error_callback)

	def _create_output_directory(self):
		self.output_in_progress = True
		# Now we need to create a copy of the checkout that can be altered.
		# For speed, we rsync over the top using the delete flag
		# to speed it up.
		self.output_dir = self._get_persistent_output_dir()

		self.logger.info("Creating editable working copy.")
		self.log_fp = self.logger.takeover_file()

		command = [
			'rsync',
			'--verbose',
			'--recursive',
			'--delete',
			'--exclude', '.svn', # Don't copy the SVN metadata.
			os.path.join(self.path) + '/',
			self.output_dir
		]

		def on_command_finish(code):
			self.output_in_progress = False
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command returned code %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				# Build a few output parameters.
				# TODO: Make this async.
				subversion_version = subprocess.check_output(['svn', '--version']).split("\n")[0].split(" ")[2].strip()
				raw_info = subprocess.check_output(['svn', 'info'], cwd=self.path)
				this_revision = "Unknown"
				for line in raw_info.split("\n"):
					if line.startswith("Revision:"):
						this_revision = line.split(":")[1].strip()

				parameters = {
					'revision': this_revision,
					'tool_version': subversion_version,
					'formatted_location': '%s (at %s)' % (self.parameters['location'], this_revision)
				}

				self.callback(self.output_dir, "Successfully switched to the appropriate revision.", parameters)
			else:
				self.error_callback("Unable to create a working output directory.")

		self.rsync = paasmaker.util.Popen(
			command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=on_command_finish,
			io_loop=self.configuration.io_loop,
			cwd=self.path
		)

	def _abort(self):
		if self.subversion_in_progress:
			self.subversion_worker.abort()
		elif self.output_in_progress:
			self.rsync.kill()

	def create_form(self, last_parameters):
		template = """
		<label>Repository URL:
		<input class="lister-target" type="text" name="parameters.location" value="%(location)s" required="required"></label>

		<label>Revision:
		<input type="text" name="parameters.revision" placeholder="HEAD"></label>
		"""

		return template % {
			'location': self._encoded_or_default(last_parameters, 'location', '')
		}

	def create_summary(self):
		return {
			'location': 'The subversion repository URL',
			'revision': 'The subversion revision to use'
		}

class SubversionGetDirectoryUpToDate(object):
	def __init__(self, configuration, directory, parameters, logger):
		self.configuration = configuration
		self.directory = directory
		self.parameters = parameters
		self.logger = logger

	def start(self, callback, error_callback):
		self.callback = callback
		self.error_callback = error_callback

		# Is it a new folder?
		subversion_test = os.path.join(self.directory, '.svn')
		if os.path.exists(subversion_test):
			# Already created. Just update it.
			command = [
				'svn',
				'update',
				'-r',
				self.parameters['revision']
			]

			self._subversion_command(command, self.checkout_complete)
		else:
			# Not yet cloned. Clone a new one.
			command = [
				'svn',
				'checkout',
				self.parameters['location'],
				'.'
			]

			self._subversion_command(command, self.checkout_complete)

	def checkout_complete(self, code):
		if code == 0:
			self.logger.info("Successfully updated local copy.")

			# And we're done.
			self.callback(self.directory)
		else:
			self.error_callback("Unable to checkout subversion repository.")

	def abort(self):
		# Kill the process and let everything catch up.
		self.subversion.kill()

	def _subversion_command(self, command, callback):
		self.log_fp = self.logger.takeover_file()

		def on_command_finish(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command returned code %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			callback(code)

		self.subversion = paasmaker.util.Popen(
			command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=on_command_finish,
			io_loop=self.configuration.io_loop,
			cwd=self.directory
		)

class SubversionSCMTest(BaseSCMTest):
	def _run_subversion_command(self, command):
		try:
			result = subprocess.check_output(
				command,
				cwd=self.working_dir,
				stderr=subprocess.PIPE # TODO: If it errors and pushes
				# a lot of output, this will block the process...
			)
			#print result
		except subprocess.CalledProcessError, ex:
			print ex.output
			raise ex

	def setUp(self):
		super(SubversionSCMTest, self).setUp()

		sample_dir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')

		# Create an example repo.
		self.repo = tempfile.mkdtemp()

		subprocess.check_output(
			['svnadmin', 'create', self.repo]
		)

		self.working_dir = tempfile.mkdtemp()

		# Check out the copy.
		self._run_subversion_command(['svn', 'checkout', 'file://' + self.repo, self.working_dir])

		# Make tags/branches/trunk.
		os.mkdir(os.path.join(self.working_dir, 'trunk'))
		os.mkdir(os.path.join(self.working_dir, 'tags'))
		os.mkdir(os.path.join(self.working_dir, 'branches'))

		# Put the example tornado files in there.
		shutil.copy(os.path.join(sample_dir, 'app.py'), os.path.join(self.working_dir, 'trunk'))
		shutil.copy(os.path.join(sample_dir, 'manifest.yml'), os.path.join(self.working_dir, 'trunk'))

		# Check them in.
		self._run_subversion_command(['svn', 'add', 'trunk'])
		self._run_subversion_command(['svn', 'add', 'tags'])
		self._run_subversion_command(['svn', 'add', 'branches'])
		self._run_subversion_command(['svn', 'commit', '-m', 'Initial checkin.'])

		# Switch to trunk.
		self._run_subversion_command(['svn', 'switch', 'file://' + self.repo + '/trunk'])

		# Create a branch.
		self._run_subversion_command(['svn', 'cp', 'file://' + self.repo + '/trunk', 'file://' + self.repo + '/branches/test', '-m', 'Create branch.'])

		# Switch the local copy to the branch.
		self._run_subversion_command(['svn', 'switch', 'file://' + self.repo + '/branches/test'])

		# Now update a file in that branch.
		open(os.path.join(self.repo, 'app.py'), 'a').write("\n# Test update\n");

		self._run_subversion_command(['svn', 'commit', '-m', 'Updated in branch.'])

		# Go back to trunk.
		self._run_subversion_command(['svn', 'switch', 'file://' + self.repo + '/trunk'])

		# Register the plugin.
		self.registry.register(
			'paasmaker.scm.subversion',
			'paasmaker.pacemaker.scm.subversion.SubversionSCM',
			{},
			'Subversion SCM'
		)

	def tearDown(self):
		# Delete the repo.
		shutil.rmtree(self.repo)
		shutil.rmtree(self.working_dir)

		super(SubversionSCMTest, self).tearDown()

	def test_working_copy(self):
		logger = self.configuration.get_job_logger('testscmsvn')
		plugin = self.registry.instantiate(
			'paasmaker.scm.subversion',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{
				'location': 'file://' + self.repo + '/trunk'
			},
			logger
		)

		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not checkout properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertFalse(os.path.exists(os.path.join(self.path, '.svn')), "Output directory still has svn metadata.")

		# Change a app.py in the source repo, then run it again.
		# This time it should update the changes, and apply them.
		open(os.path.join(self.working_dir, 'app.py'), 'a').write("\n# Test update - in trunk\n");
		self._run_subversion_command(['svn', 'commit', '-m', 'Updated in trunk.'])

		# And make sure we can now update.
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not update properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertFalse(os.path.exists(os.path.join(self.path, '.svn')), "Output directory still has svn metadata.")
		app_contents = open(os.path.join(self.path, 'app.py'), 'r').read()
		self.assertIn("Test update - in trunk", app_contents, "Local checkout was not updated.")

		# In our local repo, switch to a branch, change a file, and then try to deploy from
		# that branch.
		self._run_subversion_command(['svn', 'switch', 'file://' + self.repo + '/branches/test'])
		open(os.path.join(self.working_dir, 'app.py'), 'a').write("\n# BRANCH CHANGE\n");
		self._run_subversion_command(['svn', 'commit', '-m', 'Updated something in branch.'])

		plugin = self.registry.instantiate(
			'paasmaker.scm.subversion',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{
				'location': 'file://' + self.repo + '/branches/test'
			},
			logger
		)

		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not checkout properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertFalse(os.path.exists(os.path.join(self.path, '.svn')), "Output directory still has svn metadata.")
		app_contents = open(os.path.join(self.path, 'app.py'), 'r').read()
		self.assertIn("BRANCH CHANGE", app_contents, "Local checkout was not updated.")

		# TODO: Test the error paths in this file, as there are so many of them.
		# TODO: Test the branching thing on a real remote URL.
		# TODO: Test going to a specific revision.
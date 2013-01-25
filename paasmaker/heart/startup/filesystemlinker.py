import os
import json
import glob
import tempfile

import paasmaker
from paasmaker.pacemaker.prepare.base import BasePrepare, BasePrepareTest

import colander

class FilesystemLinkerConfigurationSchema(colander.MappingSchema):
	pass

class FilesystemLinkerParametersSchema(colander.MappingSchema):
	directories = colander.SchemaNode(
		colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Directories",
		description="List of directories to be symlinked into a persistent filesystem location."
	)

class FilesystemLinker(BasePrepare):
	"""
	Does some stuff.

	Make sure you supply relative paths. If you have multiple entries where one is a child
	directory of another, list the parent first and the child second.

	This plugin depends on the application having one (and only one) filesystem service
	allocated to it in the application manifest.
	"""
	# NOTE: This plugin can also be used to run commands prior to an instance starting.
	MODES = {
		paasmaker.util.plugin.MODE.PREPARE_COMMAND: FilesystemLinkerParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_STARTUP: FilesystemLinkerParametersSchema()
	}
	OPTIONS_SCHEMA = FilesystemLinkerConfigurationSchema()

	# - parse services out of environment variable
	# - look for protocol: directory (and only one, else error callback)
	# - foreach user parameter directory, async check:
	#   - if target (FilesystemService persistent location) exists; if not create it
	#   - if source (master version of the files in SCM) exists, copy contents of source -> target
	#   - if source exists, delete it (to be replaced in next step)
	#   - add a symlink to target
	def prepare(self, environment, instance_directory, callback, error_callback):
		if 'PM_SERVICES' not in environment:
			raise ValueError("Application environment variables haven't been set correctly.")

		services = json.loads(environment['PM_SERVICES'])
		parent_directory = None

		for service in services.values():
			if 'protocol' in service and service['protocol'] == 'directory':
				if parent_directory is not None:
					# there's more than one directory returned by this service!
					error_callback("This application has more than one filesystem service assigned, but filesystem linker plugin only supports one service.")
					return

				parent_directory = service['directory']

		if parent_directory is None:
			error_callback("Filesystem linker plugin requires a filesystem service to be assigned to the application.")
			return

		self.callback = callback
		self.error_callback = error_callback
		self.instance_directory = instance_directory
		self.parent_directory = parent_directory

		self.directories = list(self.parameters['directories'])
		self.directories.reverse()

		# check directories for nested items: it doesn't make sense
		# for the parent dir of one symlink to itself be a symlink
		dirs = list(self.parameters['directories'])
		dirs.sort()
		for i, val in enumerate(dirs):
			if len(dirs[i+1:i+2]) > 0:
				if dirs[i+1:i+2][0].startswith("%s/" % val):
					error_callback("Filesystem linker plugin parameters cannot contain nested directories: %s and %s" % (val, dirs[i+1:i+2][0]))
					return

		self._fetch_directory()

	def _fetch_directory(self):
		if len(self.directories) > 0:
			directory = self.directories.pop()
			self._process_directory(directory)
		else:
			self.callback("Linked %d directories." % len(self.parameters['directories']))

	def _process_directory(self, directory):
		persistent_path = os.path.abspath(os.path.join(self.parent_directory, directory))
		instance_application_path = os.path.abspath(os.path.join(self.instance_directory, directory))

		# first check that these are where we expect (i.e. children of instance_directory / parent_directory)
		if not persistent_path.startswith(self.parent_directory) \
			or not instance_application_path.startswith(self.instance_directory):
			self.error_callback("Filesystem linker directory %d is not a relative path or contains ../" % directory)
			return

		if not os.path.exists(persistent_path):
			try:
				os.makedirs(persistent_path)
			except OSError, ex:
				self.error_callback("Couldn't create target %s" % persistent_path, ex)
				return

		if os.path.exists(instance_application_path):
			# if the source path is a non-empty directory (i.e. there are files
			# from the SCM in there), treat those files as authoritative copies,
			# then delete the source so it can be replaced with a symlink
			files_to_copy = glob.glob(os.path.join(instance_application_path, "*"))

			if len(files_to_copy) > 0:
				command = ['cp', '-rv'] + files_to_copy + [persistent_path]
				self.log_fp = self.logger.takeover_file()

				def remove_complete(code):
					self.logger.untakeover_file(self.log_fp)
					self.logger.info("rm command returned code: %d", code)
					if code == 0:
						self.logger.info("Source directory deleted successfully (ahead of symlinking).")
						self._symlink_dir(persistent_path, instance_application_path)
					else:
						self.logger.error("Couldn't delete %s" % instance_application_path)
						self.error_callback("Couldn't delete %s" % instance_application_path)

				def copy_complete(code):
					self.logger.untakeover_file(self.log_fp)
					self.logger.info("cp command returned code: %d", code)
					if code == 0:
						self.logger.info("All files copied successfully.")
						command = ['rm', '-rfv', instance_application_path]
						self.log_fp = self.logger.takeover_file()
						paasmaker.util.Popen(
							command,
							stdout=self.log_fp,
							stderr=self.log_fp,
							on_exit=remove_complete,
							io_loop=self.configuration.io_loop
						)
					else:
						self.logger.error("Couldn't copy files from %s" % instance_application_path)
						self.error_callback("Couldn't copy files from %s" % instance_application_path)

				paasmaker.util.Popen(
					command,
					stdout=self.log_fp,
					stderr=self.log_fp,
					on_exit=copy_complete,
					io_loop=self.configuration.io_loop
				)

		else:
			self._symlink_dir(persistent_path, instance_application_path)

	def _symlink_dir(self, persistent_path, instance_application_path):
		# check that all directories up to the symlink location exist,
		# and create them if they don't (unlike the persistent path,
		# where we refuse to go a mkdir, the instance path is managed
		# by Paasmaker anyway)
		symlink_containing_dir = os.path.abspath(os.path.join(instance_application_path, '..'))
		if not os.path.exists(symlink_containing_dir):
			os.makedirs(symlink_containing_dir)

		# link from instance path to persistent path
		os.symlink(persistent_path, instance_application_path)

		# done processing this directory: check for another
		self._fetch_directory()


class FilesystemLinkerTest(BasePrepareTest):
	def setUp(self):
		super(FilesystemLinkerTest, self).setUp()
		self.logger = self.configuration.get_job_logger('teststartup_filesystemlinker')
		self.persistent_directory = os.path.join(self.tempdir, "filesystemlinker_persistent")
		self.instance_directory = os.path.join(self.tempdir, "filesystemlinker_instance")

		self.sample_env = {
			"PM_SERVICES": json.dumps(
				{ "filesystemlinker": {
					"directory": self.persistent_directory,
					"protocol": "directory"
				} }
			)
		}

		self.registry.register(
			'paasmaker.startup.filesystemlinker',
			'paasmaker.heart.startup.filesystemlinker.FilesystemLinker',
			{},
			'Filesystem Linker'
		)

	def test_no_target_and_no_source(self):
		# Basic test: neither source nor target exists, so check that the plugin created the target and made the source a symlink.
		parameters = {
			"directories": ['simple_target_directory']
		}

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemLinker did not prepare properly: %s" % self.message)

		self.assertTrue(os.path.islink(os.path.join(self.instance_directory, parameters['directories'][0])), "Symlink was not created in the instance directory.")
		self.assertTrue(os.path.exists(os.path.join(self.persistent_directory, parameters['directories'][0])), "Target directory does not appear to exist.")
		
	def test_invalid_directory_parameters(self):
		# Linked directories nested at multiple levels don't make sense (if a is a symlink, then a/b can't also be a symlink)
		parameters = {
			"directories": [
				'target_directory',
				'target_2',
				'target_directory/other_child',
				'target_2/yet_another_child'
			]
		}

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertFalse(self.success, "FilesystemLinker should have failed to prepare()")
		self.assertIn("cannot contain nested directories", self.message, "FilesystemLinker didn't report error: %s" % self.message)

	def test_multiple_no_target_no_source(self):
		# ... multiple linked directories that don't overlap should work, however.
		parameters = {
			"directories": [
				'target_directory',
				'other_directory/other_child',
				'yet_another_directory/with/yet_another_child'
			]
		}

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemLinker did not prepare properly: %s" % self.message)

		for dirname in parameters['directories']:
			self.assertTrue(os.path.islink(os.path.join(self.instance_directory, dirname)), "Symlink %s was not created in the instance directory." % dirname)
			self.assertTrue(os.path.exists(os.path.join(self.persistent_directory, dirname)), "Target directory %s does not appear to exist." % dirname)
		
	def test_has_target_no_source(self):
		# Create the target dir beforehand, and make sure the symlink still works.
		parameters = {
			"directories": [
				'target_directory/that_already_exists'
			]
		}

		target_directory = os.path.join(self.persistent_directory, parameters["directories"][0])
		source_symlink = os.path.join(self.instance_directory, parameters['directories'][0])

		os.makedirs(target_directory)
		self.assertTrue(os.path.exists(target_directory), "Target directory didn't get created during test setup.")

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemLinker did not prepare properly: %s" % self.message)

		self.assertTrue(os.path.islink(source_symlink), "Symlink was not created in the instance directory.")
		self.assertTrue(os.path.exists(target_directory), "Target directory does not appear to exist.")
		self.assertEqual(target_directory, os.path.realpath(source_symlink), "Symlink in instance directory does not point to target directory.")
		
	def test_no_target_has_source(self):
		# Create the source dir beforehand, insert two small files, and check that they're copied.
		parameters = {
			"directories": [
				'yet_another_directory'
			]
		}

		target_directory = os.path.join(self.persistent_directory, parameters["directories"][0])
		source_location = os.path.join(self.instance_directory, parameters['directories'][0])

		os.makedirs(source_location)
		test_file = os.path.join(source_location, "test")
		test_string = "FilesystemLinkerTest"

		for i in range(5):
			fp = open(test_file + str(i), 'w')
			fp.write(test_string)
			fp.close()
			self.assertTrue(os.path.exists(test_file + str(i)), "Test source file didn't get created during test setup.")

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemLinker did not prepare properly: %s" % self.message)

		self.assertTrue(os.path.islink(source_location), "Symlink was not created in the instance directory.")
		self.assertTrue(os.path.exists(target_directory), "Target directory does not appear to exist.")

		for i in range(5):
			copied_test_file = os.path.join(target_directory, "test") + str(i)
			self.assertTrue(os.path.exists(copied_test_file), "Test file doesn't appear to exist in target directory.")

			fp = open(copied_test_file)
			copied_contents = fp.read()
			fp.close()
			self.assertEqual(test_string, copied_contents, "Target directory does not appear to exist.")		

			self.assertEqual(copied_test_file, os.path.realpath(test_file + str(i)), "File path with symlink in instance directory does not point to file in target directory.")
		
	def test_has_target_and_has_source(self):
		# If both directories exist beforehand, check that a test file is copied correctly and that the subsequent symlink works.
		parameters = {
			"directories": [
				'target_directory/that_already_exists'
			]
		}

		target_directory = os.path.join(self.persistent_directory, parameters["directories"][0])
		source_location = os.path.join(self.instance_directory, parameters['directories'][0])
		test_file = os.path.join(source_location, "testtest.txt")
		test_string = "The quick brown fox jumps over the lazy dog."

		os.makedirs(target_directory)
		self.assertTrue(os.path.exists(target_directory), "Target directory didn't get created during test setup.")

		os.makedirs(source_location)
		fp = open(test_file, 'w')
		fp.write(test_string)
		fp.close()
		self.assertTrue(os.path.exists(test_file), "Test source file didn't get created during test setup.")

		plugin = self.registry.instantiate(
			'paasmaker.startup.filesystemlinker',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			self.logger
		)

		plugin.prepare(self.sample_env, self.instance_directory, self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemLinker did not prepare properly: %s" % self.message)

		self.assertTrue(os.path.islink(source_location), "Symlink was not created in the instance directory.")
		self.assertTrue(os.path.exists(target_directory), "Target directory does not appear to exist.")

		copied_test_file = os.path.join(target_directory, "testtest.txt")
		self.assertTrue(os.path.exists(copied_test_file), "Test file doesn't appear to exist in target directory.")

		# the path in test_file should now be a symlink to the target directory
		fp = open(test_file)
		contents_via_symlink = fp.read()
		fp.close()
		self.assertEqual(test_string, contents_via_symlink, "Target directory does not appear to exist.")		

		self.assertEqual(target_directory, os.path.realpath(source_location), "Symlink in instance directory does not point to target directory.")
		self.assertEqual(copied_test_file, os.path.realpath(test_file), "File path with symlink in instance directory does not point to file in target directory.")

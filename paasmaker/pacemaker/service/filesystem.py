import os

import paasmaker
from base import BaseService, BaseServiceTest
from paasmaker.util.configurationhelper import InvalidConfigurationParameterException

import colander

class FilesystemServiceConfigurationSchema(colander.MappingSchema):
	parent_directory = colander.SchemaNode(
		colander.String(),
		title="Parent directory",
		description="Parent directory of the shared filesystem. Directories for applications are created as children, so w+x permission is needed on this directory."
	)

class FilesystemServiceParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

class FilesystemService(BaseService):
	"""
	This service makes a writeable directory available to applications that request it
	(by referencing the service in a manifest file). This is useful for legacy
	applications that need to write to the filesystem on their web server (e.g. for
	cache files).

	To use this service, you must configure a ``parent_directory`` value in the
	Paasmaker config file, and use the filesystem linker startup task to make the
	directory available inside your app.

	.. WARNING::
		Applications using this service should run only on a single node, or have the
		filesystem stored on a network mount (such as NFS/SMB). Otherwise, nodes will
		have inconsistent data and users will see strange behaviour depending on which
		node they're routed to.

		This should only be used for legacy applications that have no alternative to
		filesystem storage; do not use it in new applications.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: FilesystemServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None
	}
	OPTIONS_SCHEMA = FilesystemServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def _check_options(self):
		super(FilesystemService, self)._check_options()

		# in case the user has used a relative path; note that this modifies
		# the options dict *after* Colander has performed validation
		self.options['parent_directory'] = os.path.abspath(self.options['parent_directory'])

		# check that the parent directory exists
		if not os.path.exists(self.options['parent_directory']):
			raise InvalidConfigurationParameterException("Parent directory %s does not exist." % self.options['parent_directory'])

	def create(self, name, callback, error_callback):
		full_path = os.path.join(self.options['parent_directory'], self.called_name, self._safe_name(name))

		self.logger.debug("Creating legacy filesystem storage directory: %s", str(full_path))

		try:
			os.makedirs(full_path)
		except OSError, ex:
			error_callback("Couldn't create directory", ex)
			return

		callback(
			{
				"directory": full_path,
				"protocol": "directory"
			},
			"Created directory for filesystem access"
		)

	def update(self, name, existing_credentials, callback, error_callback):
		callback(existing_credentials)

	def remove(self, name, existing_credentials, callback, error_callback):
		"""
		Remove the service and the directory it was using.
		"""
		full_path = existing_credentials['directory']
		self.logger.info("Deleting filesystem storage directory %s" % full_path)

		# Safeguard: make sure that the directory is a child of the configured parent
		if not full_path.startswith(self.options['parent_directory']):
			raise ValueError("Directory supplied to remove() is not a child of parent_directory. For safety, we're refusing to remove it.")

		command = ['rm', '-rfv', full_path]
		self.log_fp = self.logger.takeover_file()

		def remove_complete(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("rm command returned code: %d", code)
			if code == 0:
				self.logger.info("All files removed successfully.")
				callback("All files removed.")
			else:
				self.logger.error("Not all files were removed.")
				error_callback("Couldn't delete all files.")

		removeer = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=remove_complete,
			io_loop=self.configuration.io_loop,
			cwd=self.options['parent_directory'])

class FilesystemServiceTest(BaseServiceTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger("testfilesystemservice")

		self.registry.register(
			'paasmaker.service.filesystem',
			'paasmaker.pacemaker.service.filesystem.FilesystemService',
			{"parent_directory": self.configuration.get_flat('scratch_directory')},
			'Filesystem Service'
		)
		service = self.registry.instantiate(
			'paasmaker.service.filesystem',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{},
			logger=logger
		)

		service.create('test', self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemService creation was not successful.")
		self.assertEquals(len(self.credentials), 2, "FilesystemService did not return expected number of keys.")
		self.assertTrue('directory' in self.credentials, "FilesystemService did not return the directory it created.")

		fs_dir = self.credentials['directory']
		self.assertTrue(os.path.exists(fs_dir), "FilesystemService allegedly created directory %s but it appears to not exist" % fs_dir)

		service.remove('test', self.credentials, self.success_remove_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "FilesystemService deletion was not successful.")
		self.assertFalse(os.path.exists(fs_dir), "FilesystemService allegedly deleted directory %s but it appears to exist" % fs_dir)


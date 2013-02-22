
import os
import urlparse

from ..base import BaseJob
from paasmaker.util.plugin import MODE

import paasmaker
from paasmaker.common.core import constants

import colander

class DeRegisterInstanceJobSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.String())

class DeRegisterInstanceJob(BaseJob):
	"""
	A job to de-register an instance on the node.
	This means deleting it and all its files.
	"""
	MODES = {
		MODE.JOB: DeRegisterInstanceJobSchema()
	}

	def start_job(self, context):
		self.output_context = {}
		self.logger.info("De-registration of instance. Deleting all files.")

		self.instance_id = self.parameters['instance_id']

		# TODO: Check state of the instance.

		# Remove it from the instance manager. This is done regardless of success of
		# removing the files.
		try:
			self.configuration.instances.remove_instance(self.instance_id)
		except KeyError, ex:
			# Failed to find the instance. This means it's already deregistered,
			# but the server doesn't think so. So we allow this to succeed right now,
			# and the parent job will then update the database correctly.
			# So we just ignore this error.
			pass

		# Get the instance path.
		self.instance_path = self.configuration.get_instance_path(self.instance_id)

		if os.path.islink(self.instance_path):
			# It's a link. Unlink it rather than removing files.
			self.logger.info("Target is a symlink, so just removing that symlink instead.")
			os.unlink(self.instance_path)
			self._finish()
		else:
			self.log_fp = self.logger.takeover_file()

			# Sanity check - make sure that the instance path is a subpath of the heart
			# directory. For safety.
			absdir = os.path.abspath(self.instance_path)
			absdir = os.path.realpath(absdir)
			working_dir = self.configuration.get_flat('heart.working_dir')

			if not absdir.startswith(working_dir):
				raise ValueError("Instance path is not a sub path of the configured heart working directory. For safety, we're refusing to remove it.")

			# Remove it.
			command = ['rm', '-rfv', self.instance_path]

			remover = paasmaker.util.Popen(command,
				stdout=self.log_fp,
				stderr=self.log_fp,
				on_exit=self._remove_complete,
				io_loop=self.configuration.io_loop,
				cwd=self.instance_path)

	def _remove_complete(self, code):
		self.logger.untakeover_file(self.log_fp)
		self.logger.info("rm command returned code: %d", code)
		#self.configuration.debug_cat_job_log(self.logger.job_id)
		if code == 0:
			self.logger.info("All files removed successfully.")
		else:
			self.logger.warning("Not all files were removed. However, the instance is considered de-registered and can not be reused.")

		self._finish()

	def _finish(self):
		state_key = "state-%s" % self.instance_id
		self.success({state_key: constants.INSTANCE.DEREGISTERED}, "Completed successfully.")


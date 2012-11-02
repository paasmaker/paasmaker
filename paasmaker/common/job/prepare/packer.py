
import os

import paasmaker
from paasmaker.common.core import constants

class SourcePackerJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration):
		self.configuration = configuration

	def get_job_title(self):
		return "Source code packer"

	def start_job(self):
		root = self.get_root_job()
		logger = self.job_logger()

		# This is the working directory for this.
		self.path = root.source_path

		package_name = "%s_%s.tar.gz" % (root.application.id, root.version.id)
		package_path = os.path.join(self.configuration.get_flat('scratch_directory'), 'packed')
		if not os.path.exists(package_path):
			os.makedirs(package_path, 0750)

		package_full_name = os.path.join(package_path, package_name)
		root.package = package_full_name

		logger.info("Packaging source code...")
		self.log_fp = logger.takeover_file()

		pack_result = 0

		# The callback to handle source complete.
		def cleanup_complete(code):
			logger.untakeover_file(self.log_fp)
			logger.info("Finished removing temporary directory. Code %d.", code)
			#self.configuration.debug_cat_job_log(logger.job_id)
			if pack_result == 0:
				self.finished_job(constants.JOB.SUCCESS, 'Successfully packed source code.')
			else:
				self.finished_job(constants.JOB.FAILED, 'Unable to pack up source code.')

		# The callback to handle packaging completion.
		def pack_complete(code):
			logger.untakeover_file(self.log_fp)
			logger.info("Command result: %d" % code)
			pack_result = code
			if code == 0:
				logger.info("Successfully packed source code.")
			else:
				logger.error("Unable to pack up source code.")

			# Remove the working directory. This occurs regardless of
			# success or not.
			# We do this as a subprocess, so it doesn't block our process.
			# The callback to this then completes our job.
			self.log_fp = logger.takeover_file()
			cleanup_command = ['rm', '-rfv', root.source_path]

			cleanup_runner = paasmaker.util.Popen(cleanup_command,
				stdout=self.log_fp,
				stderr=self.log_fp,
				on_exit=cleanup_complete,
				cwd=self.path,
				io_loop=self.configuration.io_loop,
				env=root.environment)

		# Fire off the pack command.
		pack_command = ['tar', 'zcvf', package_full_name, '.']

		packer_runner = paasmaker.util.Popen(pack_command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=pack_complete,
			cwd=self.path,
			io_loop=self.configuration.io_loop,
			env=root.environment)
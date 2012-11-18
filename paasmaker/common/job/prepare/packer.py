
import os

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob

class SourcePackerJob(BaseJob):
	def start_job(self, context):
		output_context = {}
		# This is the working directory for this.
		self.path = context['working_path']

		package_name = "%d_%d.tar.gz" % (context['application_id'], context['application_version_id'])
		package_path = self.configuration.get_scratch_path_exists('packed')

		package_full_name = os.path.join(package_path, package_name)
		output_context['package'] = package_full_name

		self.logger.info("Packaging source code...")
		self.log_fp = self.logger.takeover_file()

		pack_result = 0

		# The callback to handle source complete.
		def cleanup_complete(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Finished removing temporary directory. Code %d.", code)
			#self.configuration.debug_cat_job_log(logger.job_id)
			if pack_result == 0:
				self.success(output_context, "Successfully packed source code.")
			else:
				self.failed("Failed to pack source code.")

		# The callback to handle packaging completion.
		def pack_complete(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command result: %d" % code)
			pack_result = code
			if code == 0:
				self.logger.info("Successfully packed source code.")
			else:
				self.logger.error("Unable to pack up source code.")

			# Remove the working directory. This occurs regardless of
			# success or not.
			# We do this as a subprocess, so it doesn't block our process.
			# The callback to this then completes our job.
			self.log_fp = self.logger.takeover_file()
			cleanup_command = ['rm', '-rfv', self.path]

			cleanup_runner = paasmaker.util.Popen(cleanup_command,
				stdout=self.log_fp,
				stderr=self.log_fp,
				on_exit=cleanup_complete,
				cwd=self.path,
				io_loop=self.configuration.io_loop,
				env=context['environment'])

		# Fire off the pack command.
		pack_command = ['tar', 'zcvf', package_full_name, '.']

		packer_runner = paasmaker.util.Popen(pack_command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=pack_complete,
			cwd=self.path,
			io_loop=self.configuration.io_loop,
			env=context['environment'])
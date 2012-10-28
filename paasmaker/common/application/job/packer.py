
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
		log_fp = logger.takeover_file()

		# The callback to handle success/failure.
		def callback(code):
			logger.untakeover_file(log_fp)
			logger.info("Command result: %d" % code)
			if code == 0:
				self.finished_job(constants.JOB.SUCCESS, 'Successfully packed source code.')
			else:
				logger.error("Unable to pack up source code.")
				self.finished_job(constants.JOB.FAILED, 'Unable to pack up source code.')

		command = ['tar', 'zcvf', package_full_name, '.']

		runner = paasmaker.util.Popen(command,
			stdout=log_fp,
			stderr=log_fp,
			on_exit=callback,
			cwd=self.path,
			io_loop=self.configuration.io_loop,
			env=root.environment)
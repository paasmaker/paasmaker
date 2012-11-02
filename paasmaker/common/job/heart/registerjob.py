
import os
import urlparse

import paasmaker
from paasmaker.common.core import constants

class RegisterJob(paasmaker.util.jobmanager.JobRunner):
	"""
	A job to register the instance on the node.
	This means downloading it, unpacking it.
	Not starting though - we'll let the pacemaker advise us of that.
	"""
	def __init__(self, configuration, instance_id):
		self.configuration = configuration
		self.instance_id = instance_id

	def get_job_title(self):
		return "Register job for %s" % self.instance_id

	def start_job(self):
		logger = self.job_logger()
		logger.info("Registration of instance. Unpacking source.")

		# Create a directory for the instance.
		instance_path = self.configuration.get_instance_path(self.instance_id)

		instance_package_container = self.configuration.get_instance_package_path()

		# Fetch the files, and unpack.
		# If the file is stored on our node, skip directly to the unpack stage.
		instance_data = self.configuration.instances.get_instance(self.instance_id)
		raw_url = instance_data['application_version']['source_path']
		logger.info("Fetching package from %s", raw_url)
		parsed = urlparse.urlparse(raw_url)

		def begin_unpacking(package_path):
			# CAUTION: This means the logger MUST be a job logger.
			# TODO: Handle this nicer...
			log_fp = logger.takeover_file()

			def unpacking_complete(code):
				logger.untakeover_file(log_fp)
				logger.info("tar command returned code: %d", code)
				#self.configuration.debug_cat_job_log(logger.job_id)
				if code == 0:
					self.finished_job(constants.JOB.SUCCESS, "Completed successfully.")
				else:
					self.finished_job(constants.JOB.FAILURE, "Failed to extract files.")

			# Begin unpacking.
			command = ['tar', 'zxvf', package_path]

			extractor = paasmaker.util.Popen(command,
				stdout=log_fp,
				stderr=log_fp,
				on_exit=unpacking_complete,
				io_loop=self.configuration.io_loop,
				cwd=instance_path)

		if parsed.scheme == 'paasmaker' and parsed.netloc == self.configuration.get_node_uuid():
			begin_unpacking(parsed.path)
		else:
			# Download it first. TODO: Do this at some stage...
			# Or check to see if we already have it cached locally,
			# and it matches the appropriate checksum.
			begin_unpacking(local_path)

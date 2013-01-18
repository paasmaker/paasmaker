
import os
import urlparse

from ..base import BaseJob
from paasmaker.util.plugin import MODE

import paasmaker
from paasmaker.common.core import constants

import colander

class RegisterInstanceJobSchema(colander.MappingSchema):
	# We don't validate the contents of below, but we do make sure
	# that we're at least supplied them.
	instance = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	instance_type = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	application_version = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	application = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	environment = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")

class RegisterInstanceJob(BaseJob):
	"""
	A job to register the instance on the node.
	This means downloading it, unpacking it.
	Not starting though - we'll let the pacemaker advise us of that.
	"""
	MODES = {
		MODE.JOB: RegisterInstanceJobSchema()
	}

	def start_job(self, context):
		self.output_context = {}
		self.logger.info("Registration of instance. Unpacking source.")

		self.instance_id = self.parameters['instance']['instance_id']

		# Create a directory for the instance.
		self.instance_path = self.configuration.get_instance_path(self.instance_id)
		instance_package_container = self.configuration.get_instance_package_path()

		if not self.parameters['instance_type']['standalone']:
			# Select a port, which goes into the output context.
			port = self.configuration.get_free_port()
			self.parameters['instance']['port'] = port
			self.configuration.port_allocator.add_allocated_port(port)
			self.output_context["port-" + self.instance_id] = port

		if not self.configuration.instances.has_instance(self.instance_id):
			# Register the instance.
			self.configuration.instances.add_instance(self.instance_id, self.parameters)

		# Fetch the files, and unpack.
		# If the file is stored on our node, skip directly to the unpack stage.
		self.instance_data = self.configuration.instances.get_instance(self.instance_id)
		raw_url = self.instance_data['application_version']['source_path']
		self.logger.info("Fetching package from %s", raw_url)
		parsed = urlparse.urlparse(raw_url)

		self.resolved_package_name = parsed.path.strip('/') # TODO: Prevent '../' and otherwise sanitise this name.
		self.resolved_package_path = os.path.join(
			self.configuration.get_scratch_path_exists('packed'),
			self.resolved_package_name
		)

		if os.path.exists(self.resolved_package_path):
			# No need to download it, it's already here!
			self.begin_unpacking(self.resolved_package_path)
		elif parsed.scheme == 'paasmaker' and parsed.netloc == self.configuration.get_node_uuid():
			# This means the file should have been here, but is not... so fail with an error.
			# TODO: Test this condition.
			self.failed("Missing package file %s which should be stored on this node.", self.resolved_package_path)
		elif parsed.scheme == 'paasmaker':
			# It's hosted on another node - for the moment we're assuming the single master
			# so go off and fetch it.
			# TODO: Test this condition.
			self.fetch_package(raw_url, parsed)
		else:
			self.failed("Unknown package scheme %s.", parsed.scheme)

	def fetch_package(self, raw_url, parsed_url):
		request = paasmaker.common.api.package.PackageDownloadAPIRequest(self.configuration)
		request.fetch(
			self.resolved_package_name,
			self._package_fetched,
			self._package_failed,
			self._package_progress
		)

	def _package_fetched(self, path, message):
		self.logger.info(message)
		self.begin_unpacking(path)

	def _package_failed(self, error, exception=None):
		self.logger.error(error)
		if exception:
			self.logger.error("Exception:", exc_info=exception)
		self.failed("Failed to download package: %s" % error)

	def _package_progress(self, size, total):
		percent = 0.0
		if total > 0:
			percent = (float(size) / float(total)) * 100
		self.logger.info("Downloaded %d of %d bytes (%0.2f%%)", size, total, percent)

	def begin_unpacking(self, package_path):
		self.log_fp = self.logger.takeover_file()

		# Begin unpacking.
		command = ['tar', 'zxvf', package_path]

		extractor = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=self.unpacking_complete,
			io_loop=self.configuration.io_loop,
			cwd=self.instance_path)

	def unpacking_complete(self, code):
		self.logger.untakeover_file(self.log_fp)
		self.logger.info("tar command returned code: %d", code)
		#self.configuration.debug_cat_job_log(logger.job_id)
		if code == 0:
			self.instance_data['runtime']['path'] = self.instance_path
			self.instance_data['instance']['state'] = constants.INSTANCE.REGISTERED
			self.configuration.instances.save()
			self.success(self.output_context, "Completed successfully.")
		else:
			self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
			self.configuration.instances.save()
			self.failed("Failed to extract files.")


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

		self.resolved_package_name = os.path.abspath(parsed.path)
		self.resolved_package_name = os.path.basename(self.resolved_package_name)
		self.resolved_package_path = os.path.join(
			self.configuration.get_scratch_path_exists('packed'),
			self.resolved_package_name
		)

		# Does the file exist locally?
		if os.path.exists(self.resolved_package_path) and os.path.isfile(self.resolved_package_path):
			# No need to download it, it's already here!
			self._begin_unpacking(self.resolved_package_path)
		else:
			# Find a plugin to fetch the package.
			fetcher_plugin_name = 'paasmaker.fetcher.%s' % parsed.scheme

			plugin_exists = self.configuration.plugins.exists(
				fetcher_plugin_name,
				paasmaker.util.plugin.MODE.FETCHER
			)

			if not plugin_exists:
				error_message = "No such fetcher %s - we don't know how to fetch this package." % fetcher_plugin_name
				self.logger.error(error_message)
				self.failed(error_message)
				return

			fetcher_plugin = self.configuration.plugins.instantiate(
				fetcher_plugin_name,
				paasmaker.util.plugin.MODE.FETCHER,
				{},
				self.logger
			)

			fetcher_plugin.fetch(
				raw_url,
				self.resolved_package_name,
				self.resolved_package_path,
				self._fetch_complete,
				self._fetch_failed
			)

	def _fetch_complete(self, path, message):
		# Success! Move onto unpacking.
		self._begin_unpacking(path)

	def _fetch_failed(self, message, exception=None):
		# Fail.
		self.logger.error(message)
		if exception:
			self.logger.error("Exception", exc_info=exception)
		self.failed(message)

	def _begin_unpacking(self, package_path):
		unpacker_plugin_name = 'paasmaker.unpacker.%s' % self.instance_data['application_version']['source_package_type']

		plugin_exists = self.configuration.plugins.exists(
			unpacker_plugin_name,
			paasmaker.util.plugin.MODE.UNPACKER
		)

		if not plugin_exists:
			error_message = "No such unpacker %s - we don't know how to unpack this package." % unpacker_plugin_name
			self.logger.error(error_message)
			self.failed(error_message)
			return

		unpacker_plugin = self.configuration.plugins.instantiate(
			unpacker_plugin_name,
			paasmaker.util.plugin.MODE.UNPACKER,
			{},
			self.logger
		)

		def unpack_success(message):
			self.logger.info(message)
			# Completed. Everything should now be set up.
			self.instance_data['runtime']['path'] = self.instance_path
			self.instance_data['instance']['state'] = constants.INSTANCE.REGISTERED
			self.configuration.instances.save()
			self.success(self.output_context, "Completed successfully.")

		def unpack_failure(self, message, exception=None):
			# Fail.
			self.logger.error(message)
			if exception:
				self.logger.error("Exception", exc_info=exception)

			self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
			self.configuration.instances.save()
			self.failed("Failed to unpack files.")

		unpacker_plugin.unpack(
			package_path,
			self.instance_path,
			self.instance_data['application_version']['source_path'],
			unpack_success,
			unpack_failure
		)
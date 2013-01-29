
import os

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob

class SourcePackerJob(BaseJob):
	def start_job(self, context):
		output_context = {}
		# This is the working directory for this.
		self.path = context['working_path']

		package_prefix = "%d_%d.tar.gz" % (context['application_id'], context['application_version_id'])
		package_path = self.configuration.get_scratch_path_exists('packed')

		package_full_prefix = os.path.join(package_path, package_prefix)

		self.logger.info("Packaging source code...")
		# Locate a suitable plugin to do this.
		packer_plugin_name = 'paasmaker.packer.default'
		self.logger.debug("%s", str(context))
		if 'preferred_packer' in context:
			packer_plugin_name = 'paasmaker.packer.%s' % context['preferred_packer']

		plugin_exists = self.configuration.plugins.exists(
			packer_plugin_name,
			paasmaker.util.plugin.MODE.PACKER
		)

		if not plugin_exists:
			if 'preferred_packer' in context:
				error_message = "The preferred packer %s was not found." % packer_plugin_name
			else:
				error_message = "Your Paasmaker configuration is incomplete. No default source packer plugin is configured."

			self.logger.error(error_message)
			self.failed(error_message)
			return

		packer_plugin = self.configuration.plugins.instantiate(
			packer_plugin_name,
			paasmaker.util.plugin.MODE.PACKER,
			{},
			self.logger
		)

		def pack_complete(pack_type, pack_file, checksum, message):
			# Pack complete. Add output to the context, and pass it on.
			self.logger.info(message)

			output_context['package_type'] = pack_type
			output_context['package_file'] = pack_file
			output_context['package_checksum'] = checksum

			self.success(output_context, "Completed packing source code.")
			# end of pack_complete()

		def pack_failed(message, exception=None):
			# Handle a failure to pack.
			self.logger.error(message)
			if exception:
				self.logger.error("Exception", exc_info=exception)
			self.failed(message)
			# end of pack_failed()

		packer_plugin.pack(
			context['working_path'],
			package_full_prefix,
			pack_complete,
			pack_failed
		)

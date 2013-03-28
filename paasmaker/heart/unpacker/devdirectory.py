
import os
import urlparse

from base import BaseUnpacker, BaseUnpackerTest
import paasmaker

import colander

class DevDirectoryUnpacker(BaseUnpacker):
	API_VERSION = "0.9.0"

	def unpack(self, package_path, target_path, original_url, callback, error_callback):
		# We need to parse the directory out of the original URL.
		parsed = urlparse.urlparse(original_url)

		real_package_path = parsed.path

		if not os.path.exists(real_package_path):
			error_message = "Development path %s does not exist." % real_package_path
			self.logger.error(error_message)
			error_callback(error_message)
			return

		# The goal here is to symlink package_path to target_path.
		# Remove target path first. Paasmaker would have already created
		# this directory for us, and we need to remove it to make way for
		# our symlink. Also note that we only rmdir() it, because if it
		# contains other files we want it to fail.
		os.rmdir(target_path)

		# And symlink it.
		self.logger.debug("User directory: %s", real_package_path)
		self.logger.debug("Target instance path: %s", target_path)
		os.symlink(real_package_path, target_path)

		# And we're done.
		callback("Completed linking development directory.")
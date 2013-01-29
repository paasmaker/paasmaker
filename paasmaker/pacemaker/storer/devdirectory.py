
import os
import shutil

from base import BaseStorer, BaseStorerTest
import paasmaker

import colander

class DevDirectoryStorer(BaseStorer):

	def store(self, package_file, package_checksum, package_type, callback, error_callback):
		# Just generate a URL to that directory.
		source_path = "devdirectory://%s%s" % (self.configuration.get_node_uuid(), package_file)
		callback(source_path, "Stored package successfully.")
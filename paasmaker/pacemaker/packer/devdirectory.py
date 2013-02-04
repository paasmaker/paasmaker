
import os
import shutil

from base import BasePacker, BasePackerTest
import paasmaker

import colander

class DevDirectoryPacker(BasePacker):
	API_VERSION = "0.9.0"

	def pack(self, directory, pack_name_prefix, callback, error_callback):
		# Just emit the same directory.
		callback(
			'devdirectory',
			directory,
			'no-checksum-applicable',
			"Successfully recorded directory."
		)
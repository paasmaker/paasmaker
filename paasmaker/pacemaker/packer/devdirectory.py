
import os
import shutil

from base import BasePacker, BasePackerTest
import paasmaker

import colander

class DevDirectoryPacker(BasePacker):
	def pack(self, directory, pack_name_prefix, callback, error_callback):
		# Just emit the same directory.
		callback(
			'devdirectory',
			directory,
			'no-checksum-applicable',
			"Successfully recorded directory."
		)
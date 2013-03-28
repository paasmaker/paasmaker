#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
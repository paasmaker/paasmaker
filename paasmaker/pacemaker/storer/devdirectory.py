#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import shutil

from base import BaseStorer, BaseStorerTest
import paasmaker

import colander

class DevDirectoryStorer(BaseStorer):
	API_VERSION = "0.9.0"

	def store(self, package_file, package_checksum, package_type, callback, error_callback):
		# Just generate a URL to that directory.
		source_path = "devdirectory://%s%s" % (self.configuration.get_node_uuid(), package_file)
		callback(source_path, "Stored package successfully.")
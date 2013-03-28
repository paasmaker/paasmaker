#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import shutil

from base import BaseFetcher, BaseFetcherTest
import paasmaker

import colander

class PaasmakerNodeFetcher(BaseFetcher):
	API_VERSION = "0.9.0"

	def fetch(self, url, remote_filename, target_filename, callback, error_callback):
		# Use the API to fetch it from the appropriate node.
		def package_fetched(path, message):
			self.logger.info(message)
			callback(path, message)

		def package_failed(error, exception=None):
			error_callback(error, exception=exception)

		def package_progress(size, total):
			percent = 0.0
			if total > 0:
				percent = (float(size) / float(total)) * 100
			self.logger.info("Downloaded %d of %d bytes (%0.2f%%)", size, total, percent)

		request = paasmaker.common.api.package.PackageDownloadAPIRequest(self.configuration)
		request.fetch(
			remote_filename,
			package_fetched,
			package_failed,
			progress_callback=package_progress,
			output_file=target_filename
		)

class PaasmakerNodeFetcherTest(BaseFetcherTest):
	def test_simple(self):
		# TODO: Write unit tests for this.
		pass
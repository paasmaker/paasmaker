
import urlparse

from base import BaseFetcher, BaseFetcherTest
import paasmaker

import colander

class DevDirectoryFetcher(BaseFetcher):
	API_VERSION = "0.9.0"

	def fetch(self, url, remote_filename, target_filename, callback, error_callback):
		parsed = urlparse.urlparse(url)

		if parsed.netloc != self.configuration.get_node_uuid():
			# This package didn't initiate from this node.
			error_callback("Attempting to use a dev directory on a different node from which it was created. This is not supported.")
			return

		# Just emit the remote_filename as the path, as it's a directory
		# that should be linked.
		callback(
			remote_filename,
			"Emitted development directory."
		)
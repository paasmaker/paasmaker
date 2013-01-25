
import logging
import os
import urllib

import paasmaker
from apirequest import APIRequest, APIResponse

import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class PackageSizeAPIRequest(APIRequest):
	"""
	Get the size of a package from the remote server.
	Used to determine if the file exists, and also it's
	total size for progress updates.
	"""
	def __init__(self, *args, **kwargs):
		super(PackageSizeAPIRequest, self).__init__(*args, **kwargs)
		self.package = None
		self.method = 'GET'

	def set_package(self, package):
		"""
		Set the name of the package that should be fetched.

		:arg str package: The name of the package.
		"""
		self.package = package

	def get_endpoint(self):
		return '/files/package/size?%s' % urllib.urlencode([('name', self.package)])

# TODO: Can only download from the master at the moment. This requires
# changes to the pacemaker to allow it to locate the correct location for the file.
# That won't be too hard, as the URL also contains the UUID of the node that has
# the file.
class PackageDownloadAPIRequest(APIRequest):
	"""
	An API request to fetch a package from a remote node, storing
	it locally, and providing progress reports as it downloads.
	"""
	def __init__(self, configuration):
		self.configuration = configuration

	def _get_output_path(self):
		# Determine the automatic destination path for the package.
		package_path = self.configuration.get_scratch_path_exists('packed')
		full_path = os.path.join(package_path, self.package)
		return full_path

	def fetch(self, package, callback, error_callback, progress_callback=None, output_file=None):
		"""
		Fetch the package from the remote server.

		:arg str package: The package name to fetch.
		:arg callable callback: The callback for when the package is downloaded.
		:arg callable error_callback: The callback to call if an error occurs.
		:arg callback progress_callback: A progress callback, called periodically
			with status of the download. It is called with two arguments, position,
			in bytes, and the total size, in bytes.
		:arg str output_file: If supplied, write the resulting file to this path,
			clobbering any existing file at that path. If not supplied,
			an appropriate location is automatically determined for the file.
		"""
		self.package = package
		self.callback = callback
		self.error_callback = error_callback
		self.progress_callback = progress_callback

		if output_file:
			self.output_file = output_file
		else:
			self.output_file = self._get_output_path()

		# Begin by fetching the size of the file.
		# This also indicates if it exists or not.
		request = PackageSizeAPIRequest(self.configuration)
		request.set_package(self.package)
		request.send(self._got_size)

	def _got_size(self, response):
		if not response.success:
			# Failed to get the size.
			self.error_callback("".join(response.errors))
		else:
			# Store the size.
			self.total_size = response.data['size']

			# Open the target file.
			self.package_fp = open(self.output_file, 'w')

			# And proceed to download the file.
			endpoint = self.get_master() + '/files/package/download?%s' % urllib.urlencode([('name', self.package)])
			headers = {}
			headers['Auth-Paasmaker'] = self.configuration.get_flat('node_token')

			request = tornado.httpclient.HTTPRequest(
				endpoint,
				headers=headers,
				streaming_callback=self._on_file_block
			)
			client = tornado.httpclient.AsyncHTTPClient(io_loop=self.configuration.io_loop)
			client.fetch(request, self._on_request_complete)

	def _on_file_block(self, block):
		if block == '':
			# End of transfer.
			self.package_fp.close()
		else:
			# Write it out, and let our progress callback know.
			self.package_fp.write(block)
			position = self.package_fp.tell()
			if self.progress_callback:
				self.progress_callback(position, self.total_size)

	def _on_request_complete(self, response):
		if response.error:
			self.error_callback(response.error)
		else:
			self.callback(self.output_file, "Transferred %d bytes successfully." % self.total_size)
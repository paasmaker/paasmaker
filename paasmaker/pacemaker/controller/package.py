import logging
import os
import tempfile
import subprocess

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class PackageFetchSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String())

class PackageRootController(BaseController):
	def _find_package_file(self):
		valid_data = self.validate_data(PackageFetchSchema())

		package_path = self.configuration.get_scratch_path_exists('packed')
		full_path = os.path.join(package_path, self.params['name'])

		if not os.path.exists(full_path):
			logger.debug("Couldn't find package at %s", full_path)
			raise tornado.web.HTTPError(404, "No such package.")

		return full_path

class PackageSizeController(PackageRootController):
	# Only other nodes can grab files.
	AUTH_METHODS = [BaseController.NODE]

	def get(self):
		# Force JSON response.
		self._set_format('json')

		# Try to find the package.
		package = self._find_package_file()

		self.add_data('size', os.path.getsize(package))
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/files/package/size", PackageSizeController, configuration))
		return routes

class PackageDownloadController(PackageRootController):
	# Only other nodes can grab files.
	AUTH_METHODS = [BaseController.NODE]
	CHUNK_SIZE = 1024 * 200 # 200KB

	@tornado.web.asynchronous
	def get(self):
		# Try to find the package.
		package = self._find_package_file()

		# Set the content type. Just something generic.
		self.add_header('Content-Type', 'application/octet-stream')

		# Open and start streaming the file.
		self.fp = open(package, 'r')
		self._stream_section()

	def _stream_section(self):
		data = self.fp.read(self.CHUNK_SIZE)
		if data == '':
			# Finished!
			self.fp.close()
			self.finish()
		else:
			# Write it, flush it, and call us back
			# when it's sent so we can send the next part.
			self.write(data)
			self.flush(callback=self._stream_section)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/files/package/download", PackageDownloadController, configuration))
		return routes

class PackageControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = PackageDownloadController.get_routes({'configuration': self.configuration})
		routes.extend(PackageSizeController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def tearDown(self):
		if hasattr(self, 'temp_output'):
			os.unlink(self.temp_output)
		super(PackageControllerTest, self).tearDown()

	def _package_complete(self, path, message):
		self.stop(message)

	def test_simple(self):
		# Set up a dummy file.
		dummy_package = '1_1.tar.gz'
		dummy_path = self.configuration.get_scratch_path_exists('packed')
		dummy_full = os.path.join(dummy_path, dummy_package)

		open(dummy_full, 'w').write("test" * 1024 * 1024) # 4MB of data.

		source_checksum = subprocess.check_output(['md5sum', dummy_full]).split(' ')[0]

		self.temp_output = tempfile.mkstemp()[1]

		# Now try to fetch it.
		def progress_callback(position, total):
			logger.debug("Got %d of %d bytes.", position, total)

		# NOTE: We need to override the output file here, because otherwise it would overwrite itself...
		request = paasmaker.common.api.package.PackageDownloadAPIRequest(self.configuration)
		request.fetch(dummy_package, self._package_complete, self.stop, progress_callback, output_file=self.temp_output)
		response = self.wait()

		self.assertIn("Transferred", response, "Result was not successful.")

		result_checksum = subprocess.check_output(['md5sum', self.temp_output]).split(' ')[0]

		self.assertEquals(source_checksum, result_checksum, "Downloaded file isn't the same.")

		# Try again, with an invalid path.
		request = paasmaker.common.api.package.PackageDownloadAPIRequest(self.configuration)
		request.fetch('1_2.tar.gz', self._package_complete, self.stop, progress_callback, output_file=self.temp_output)
		response = self.wait()

		self.assertIn("404", response, "Result was not an error.")

		# Make sure it didn't clobber the output file.
		result_checksum = subprocess.check_output(['md5sum', self.temp_output]).split(' ')[0]
		self.assertEquals(source_checksum, result_checksum, "Clobbered output file.")
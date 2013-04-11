#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import os
import urllib
import sys
import json

import paasmaker
from apirequest import APIRequest, APIResponse

import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ServiceExportAPIRequest(APIRequest):
	"""
	An API to export a service from the Pacemaker, reporting
	status as it downloads.
	"""
	def __init__(self, configuration=None):
		super(ServiceExportAPIRequest, self).__init__(configuration)
		self.service_id = None
		self.method = 'GET'
		self.params = {}

	def set_service_id(self, service_id):
		"""
		Set the service ID that you want to export.

		:arg int service_id: The service ID to export.
		"""
		self.service_id = service_id

	def set_parameters(self, parameters):
		"""
		Set the parameters passed in to the export plugin.

		:arg dict parameters: The parameters for the export plugin.
		"""
		self.params['parameters'] = parameters
		self.method = 'POST'

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def fetch(self, callback, error_callback, stream_callback=None, progress_callback=None, output_file=None):
		"""
		Export the service from the remote server.

		:arg int service_id: The service to export.
		:arg callable callback: The callback for when the package is downloaded.
		:arg callable error_callback: The callback to call if an error occurs.
		:arg callable stream_callback: The callback to call when a data chunk is received.
			If None, it's not called at all.
		:arg callback progress_callback: A progress callback, called periodically
			with status of the export. It's called with a single argument, which
			is the number of byte received.
		:arg str output_file: If supplied, write the resulting file to this path,
			clobbering any existing file at that path. If not supplied,
			an appropriate location is automatically determined for the file,
			relative to the current working directory. This is based on the filename
			supplied from the server. If this argument is set to "-", the output
			is printed directly to stdout.
		"""
		self.is_buffering = True
		self.buffered_data = ""

		self.output_fp = None
		self.output_is_stdout = False
		self.received_bytes = 0

		if output_file is not None:
			# Open the target output file.
			if output_file == '-':
				# Write directly to stdout.
				self.output_fp = sys.stdout
				self.output_is_stdout = True
			else:
				# Open the target file.
				# This will clobber it.
				self.output_fp = open(output_file, 'w')

		def complete(response):
			if not self.output_is_stdout and self.output_fp is not None:
				self.output_fp.flush()
				self.output_fp.close()

			if response.code == 200:
				callback("Successfully exported service.")
			else:
				# Why do we buffer the error and return it from the buffer?
				# As soon as we use the stream_callback function, the final
				# response doesn't contain the body.
				error_callback("Failed to export service - response code %d.\n%s" % (response.code, self.buffered_data))

		def header_callback(header_line):
			# Check the header lines.
			# As soon as we get the header that indicates that it's ok,
			# stop buffering output.
			if "X-Paasmaker-Service-Export-Success" in header_line:
				self.is_buffering = False

			if "Content-Disposition" in header_line:
				# This contains the filename.
				# This is a crude parser.
				bits = header_line.split('=')
				filename = bits[1].strip()

				# Open up the target file.
				if output_file is None:
					self.output_fp = open(filename, 'w')

		def stream_callback(data):
			self.received_bytes += len(data)
			if self.is_buffering:
				self.buffered_data += data
			else:
				if len(self.buffered_data) > 0:
					self.output_fp.write(self.buffered_data)
					self.buffered_data = ''

				self.output_fp.write(data)

			if progress_callback:
				progress_callback(self.received_bytes)

		if not self.target:
			self.target = self.get_master()

		headers = {}
		headers['Auth-Paasmaker'] = self.authvalue
		endpoint = self.target + self.get_endpoint() + '?format=json'

		kwargs = {}
		kwargs['method'] = self.method
		if self.method == 'POST':
			kwargs['body'] = json.dumps(self.build_payload())
		kwargs['headers'] = headers
		kwargs['request_timeout'] = 0
		kwargs['follow_redirects'] = False

		request = tornado.httpclient.HTTPRequest(
			endpoint,
			streaming_callback=stream_callback,
			header_callback=header_callback,
			**kwargs
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, complete)

	def get_endpoint(self):
		return '/service/export/%d' % self.service_id

class ServiceImportAPIRequest(APIRequest):
	"""
	Import a service. This submits a job on the server, which you can follow.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		self.params['parameters'] = {}
		self.service_id = None
		super(ServiceImportAPIRequest, self).__init__(*args, **kwargs)

	def set_service(self, service_id):
		"""
		Set the service ID to import for.
		"""
		self.service_id = service_id

	def set_uploaded_file(self, unique_identifier):
		"""
		Set the uploaded file identifier to use for this import.
		"""
		self.params['uploaded_file'] = unique_identifier

	def set_parameters(self, parameters):
		"""
		Set the import parameters for this import.
		"""
		self.params['parameters'] = parameters

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/service/import/%d' % self.service_id
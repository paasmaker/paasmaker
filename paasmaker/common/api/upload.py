
import logging
import os
import json
import urllib

import paasmaker
from apirequest import APIRequest, APIResponse

import requests
import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

UPLOAD_CHUNK_SIZE = 1024 * 1024 # 1MB at once.

class UploadFileAPIRequest(APIRequest):
	def get_endpoint(self):
		return "/files/upload"

	def send_file(self, filename, progress_callback, finished_callback, error_callback):
		# Split and send the file.
		if self.authmethod == 'node':
			raise ValueError("You can not upload files with node authentication. Use user authentication instead.")

		# Store callbacks.
		self.progress_callback = progress_callback
		self.finished_callback = finished_callback
		self.error_callback = error_callback

		# Prepare internal variables.
		self.variables = {
			'resumableChunkNumber': 1,
			'resumableChunkSize': UPLOAD_CHUNK_SIZE,
			'resumableTotalSize': os.path.getsize(filename),
			'resumableIdentifier': "%d-%s" % (os.path.getsize(filename), os.path.basename(filename)),
			'resumableFilename': filename,
			'resumableRelativePath': filename,
			'format': 'json'
		}

		# Open up the file and get started.
		logger.info("Uploading from local file %s", filename)
		self.fp = open(filename, 'r')
		self._check_exists()

	def _check_exists(self):
		if not self.target:
			self.target = self.get_master()

		endpoint = self.target + self.get_endpoint()
		endpoint += '?' + urllib.urlencode(self.variables)
		kwargs = {}
		kwargs['method'] = 'GET'
		kwargs['headers'] = {'User-Token': self.authvalue}
		kwargs['follow_redirects'] = False

		request = tornado.httpclient.HTTPRequest(endpoint, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self._on_exists_result)

	def _on_exists_result(self, response):
		if response.error:
			# No, chunk does not exist on the server.
			logger.debug("Chunk doesn't exist on server (%s) so sending.", response.error)
			self._send_chunk_start()
		else:
			# Yes, it does.
			# Seek past it in the local file, and skip to the next chunk.
			logger.debug("Chunk does exist on server, skipping.")
			self.fp.seek(self.variables['resumableChunkSize'], 1)
			self.variables['resumableChunkNumber'] += 1
			self.last_response = response
			self._check_exists()

	def _send_chunk_start(self):
		logger.debug("Reading %d bytes from file...", self.variables['resumableChunkSize'])
		blob = self.fp.read(self.variables['resumableChunkSize'])

		if blob == '':
			# End of file.
			logger.info("Finished uploading file.")
			self.fp.close()
			self.finished_callback(json.loads(self.last_response.body))
		else:
			# Send it along.
			file_body = self._pack_file_segment(self.variables, blob)

			if not self.target:
				self.target = self.get_master()

			endpoint = self.target + self.get_endpoint()
			kwargs = {}
			kwargs['method'] = 'POST'
			kwargs['body'] = file_body['body']
			kwargs['headers'] = {
				'User-Token': self.authvalue,
				'Content-Type': file_body['mimetype']
			}

			request = tornado.httpclient.HTTPRequest(endpoint, **kwargs)
			client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
			client.fetch(request, self._on_chunk_sent)

	def _on_chunk_sent(self, response):
		self.last_response = response
		if response.error:
			# Failure. Abort.
			logger.error(response.error)
			self.fp.close()
			self.error_callback(json.loads(response.body))
		else:
			self.variables['resumableChunkNumber'] += 1
			# Call the progress callback.
			self.progress_callback(
				self.fp.tell(),
				self.variables['resumableTotalSize']
			)
			# Check and possibly send the next one.
			self._check_exists()

	def _pack_file_segment(self, variables, filedata):
		# Use the requests module to prepare the file data for us.
		files = [('file.data', filedata)]
		req = requests.Request(data=variables, files=files)
		body, mimetype = req._encode_files(files)
		return {
			'body': body,
			'mimetype': mimetype
		}
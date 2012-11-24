
import logging
import os
import json

import paasmaker

import requests
import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

UPLOAD_CHUNK_SIZE = 1024 * 200 # 200kB at once.

class UploadFileAPIRequest(paasmaker.util.APIRequest):
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
			'resumableChunkNumber': 0, # We increment this to 1 on the first start.
			'resumableChunkSize': UPLOAD_CHUNK_SIZE,
			'resumableTotalSize': os.path.getsize(filename),
			'resumableIdentifier': filename,
			'resumableFilename': filename,
			'resumableRelativePath': filename
		}

		# Open up the file and get started.
		logger.info("Uploading from local file %s", filename)
		self.fp = open(filename, 'r')
		self._send_chunk_start()

	def _send_chunk_start(self, last_response=None):
		self.variables['resumableChunkNumber'] += 1
		logger.debug("Reading %d bytes from file...", self.variables['resumableChunkSize'])
		blob = self.fp.read(self.variables['resumableChunkSize'])

		if blob == '':
			# End of file.
			logger.info("Finished uploading file.")
			self.fp.close()
			self.finished_callback(json.loads(last_response.body))
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
		if response.error:
			# Failure. Abort.
			logger.error(response.error)
			self.fp.close()
			self.error_callback(json.loads(response.body))
		else:
			# Call the progress callback.
			self.progress_callback(
				self.fp.tell(),
				self.variables['resumableTotalSize']
			)
			# Send the next one.
			self._send_chunk_start(response)

	def _pack_file_segment(self, variables, filedata):
		# Use the requests module to prepare the file data for us.
		files = [('file.data', filedata)]
		req = requests.Request(data=variables, files=files)
		body, mimetype = req._encode_files(files)
		return {
			'body': body,
			'mimetype': mimetype
		}
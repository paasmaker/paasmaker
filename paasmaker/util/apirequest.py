#!/usr/bin/env python

import paasmaker
import json
import tornado

class APIResponse():
	errors = []
	warnings = []
	data = {}
	success = False

	def __init__(self, response):
		if response.error:
			self.errors.append(str(response.error))
		else:
			if response.body[0] == '{' and response.body[-1] == '}':
				try:
					parsed = json.loads(response.body)
					self.errors.extend(parsed['errors'])
					self.warnings.extend(parsed['warnings'])
					self.data = parsed['data']
					self.raw = response

				except ValueError, ex:
					self.errors.append("Unable to parse JSON: " + str(ex))
				except KeyError, ex:
					self.errors.append("Response was malformed: " + str(ex))
			else:
				self.errors.append("Returned response was not JSON.")

		if len(self.errors) == 0:
			self.success = True

class APIRequest():
	def __init__(self, configuration, io_loop=None):
		self.configuration = configuration
		self.io_loop = io_loop

	def send(self, endpoint, payload, callback, **kwargs):
		# Build what we're sending.
		data = {}
		data['data'] = payload
		data['auth'] = { 'method': 'node', 'value': self.configuration.get_flat('auth_token') }

		encoded = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)

		kwargs['body'] = encoded
		# Always a POST, because we're sending a body.
		kwargs['method'] = 'POST'
		# Don't follow redirects - this is an API request.
		kwargs['follow_redirects'] = False

		# The function called when it returns.
		# It's a closure to preserve the callback provided.
		def our_callback(response):
			# Parse and handle what came back.
			our_response = APIResponse(response)
			# And call the caller back.
			callback(our_response)

		# Build and make the request.
		request = tornado.httpclient.HTTPRequest(endpoint, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, our_callback)

# TODO: Add unit tests!

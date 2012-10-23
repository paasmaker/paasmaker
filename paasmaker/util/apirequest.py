import paasmaker
import json
import tornado
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class APIResponse(object):
	def __init__(self, response):
		self.errors = []
		self.warnings = []
		self.data = {}
		self.success = False

		if response.error:
			logger.error("API request failed with error: %s", response.error)
			self.errors.append(str(response.error))
		else:
			logger.debug("Raw API response body: %s", response.body)
			if response.body[0] == '{' and response.body[-1] == '}':
				try:
					parsed = json.loads(response.body)
					self.errors.extend(parsed['errors'])
					self.warnings.extend(parsed['warnings'])
					self.data = parsed['data']
					self.raw = response

				except ValueError, ex:
					self.errors.append("Unable to parse JSON: " + str(ex))
					self.errors.append("Supplied JSON: " + response.body)
				except KeyError, ex:
					self.errors.append("Response was malformed: " + str(ex))
			else:
				self.errors.append("Returned response was not JSON.")

		if len(self.errors) == 0:
			self.success = True
		else:
			logger.error("API request failed with the following errors:")
			for error in self.errors:
				logger.error("- %s", error)

class APIRequest(object):
	def __init__(self, configuration):
		self.configuration = configuration
		self.target = None
		if configuration:
			self.authmethod = 'node'
			self.authvalue = self.configuration.get_flat('auth_token')
		else:
			self.authmethod = None
			self.authvalue = None

	def set_apikey_auth(self, key):
		self.authmethod = 'token'
		self.authvalue = key

	def set_nodekey_auth(self, key):
		self.authmethod = 'node'
		self.authvalue = key

	def build_payload(self):
		# Override in your subclass.
		return {}

	def get_master(self):
		# TODO: SSL ?
		return "http://%s:%d" % (self.configuration.get_flat('master_host'), self.configuration.get_flat('master_port'))

	def get_endpoint(self):
		# Override in your subclass to change the URI.
		return '/'

	def set_target(self, target):
		if isinstance(target, basestring):
			self.target = target
		elif isinstance(target, paasmaker.model.Node):
			self.target = "http://%s:%d" % (target.route, target.apiport)
		else:
			raise ValueError("Target is not a string or Node object.")

	def process_response(self, response):
		# For overriding in your subclasses, if it's all self contained.
		# Note that the supplied callback, if provided, is called after this.
		pass

	def send(self, callback=None, **kwargs):
		# Build what we're sending.
		data = {}
		data['data'] = self.build_payload()
		data['auth'] = { 'method': self.authmethod, 'value': self.authvalue }

		encoded = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)

		kwargs['body'] = encoded
		# Always a POST, because we're sending a body.
		kwargs['method'] = 'POST'
		# Don't follow redirects - this is an API request.
		kwargs['follow_redirects'] = False

		logger.debug("In send() of API request of type %s", type(self))
		logger.debug("Payload sending to server: %s", encoded)

		# The function called when it returns.
		# It's a closure to preserve the callback provided.
		def our_callback(response):
			# Parse and handle what came back.
			our_response = APIResponse(response)
			# Use the built in response processor.
			self.process_response(our_response)
			# And call the user defined callback back.
			if callback:
				callback(our_response)

		if not self.target:
			self.target = self.get_master()

		# Build and make the request.
		endpoint = self.target + self.get_endpoint()
		if endpoint.find('?') == -1:
			endpoint += '?format=json'
		else:
			endpoint += '&format=json'
		logger.debug("Endpoint for request: %s", endpoint)
		request = tornado.httpclient.HTTPRequest(endpoint, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.configuration.io_loop)
		client.fetch(request, our_callback)

# TODO: Add unit tests!

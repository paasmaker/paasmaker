
import json
import logging

import paasmaker

import tornado
from ws4py.client.tornadoclient import TornadoWebSocketClient

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class APIResponse(object):
	"""
	This class encapsulates the contents of an API response from the
	server. It is supplied via a callback. Once you have the class,
	the following instance attributes are available for you to read:

	* **errors** - a list of errors from the remote server, or an empty
	  list if there are no errors.
	* **warnings** - a list of warnings from the remote server, or an empty
	  list if there are no warnings.
	* **data** - a dict containing the decoded response from the server.
	* **success** - a boolean flag that indicates if the request was
	  successful. It's considered successful if there were no errors
	  and the response code was 200.
	"""
	def __init__(self, response):
		self.errors = []
		self.warnings = []
		self.data = {}
		self.success = False

		logger.debug("Raw API response body: %s", response.body)
		if response.body and response.body[0] == '{' and response.body[-1] == '}':
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

		if response.error:
			logger.error("API request failed with error: %s", response.error)
			self.errors.append(str(response.error))

		if len(self.errors) == 0:
			self.success = True
		else:
			logger.error("API request failed with the following errors:")
			for error in self.errors:
				logger.error("- %s", error)

class APIRequest(object):
	"""
	A base class for API requests. Provides helpers for other API request
	classes.
	"""

	def __init__(self, configuration=None):
		"""
		Sets up a new APIRequest object. If overriding, be sure to call
		the parent with the configuration object first, and then do your
		setup. Most commonly you'll override this to change the HTTP
		method that this class uses, as the default is POST.

		:arg Configuration configuration: The configuration object to use,
			or None if you don't have one. If you don't have one,
			you must be sure to set a target and appropriate authentication
			before making the request. Also, it will use the global Tornado
			IO loop in this case.
		"""
		self.configuration = configuration
		self.target = None
		self.method = 'POST'
		if configuration:
			self.authmethod = 'nodeheader'
			self.authvalue = self.configuration.get_flat('node_token')
			self.io_loop = configuration.io_loop
		else:
			self.authmethod = None
			self.authvalue = None
			self.io_loop = tornado.ioloop.IOLoop.instance()

	def duplicate_auth(self, request):
		"""
		Duplicate the authentication details from the given request.
		Useful when doing subrequests internally.

		:arg APIRequest request: The request to copy the authentication
			details from.
		"""
		self.authmethod = request.authmethod
		self.authvalue = request.authvalue
		self.target = request.target

	def set_apikey_auth(self, key):
		"""
		Set this request to use a user-based API key,
		with the supplied key.

		:arg str key: The User API key to present to the
			server.
		"""
		self.authmethod = 'tokenheader'
		self.authvalue = key

	def set_nodekey_auth(self, key):
		"""
		Set this request to use node-key authentication.

		:arg str key: The Node API key to present to the server.
		"""
		self.authmethod = 'nodeheader'
		self.authvalue = key

	def set_superkey_auth(self, key=None):
		"""
		Set this request to use super-key authentication.
		If no key is supplied, it will attempt to read the super
		key from the configuration object.

		:arg str key: The super key to present to the server.
		"""
		self.authmethod = 'superheader'
		if key:
			self.authvalue = key
		else:
			# TODO: More error checking here.
			self.authvalue = self.configuration.get_flat('pacemaker.super_token')

	def build_payload(self):
		"""
		Build the payload of the request. Return a dict that contains
		the payload that will be send to the server.

		Your subclass should override this function.
		"""
		return {}

	def async_build_payload(self, payload, callback):
		"""
		Build the payload of the request, and call the callback with the
		payload. This allows your code to use other callbacks rather than
		synchronous code. Modify the supplied payload dict, but also
		pass that dict to the callback.

		If you don't implement this function, a default implementation
		is provided.

		:arg dict payload: The payload to modify.
		:arg callable callback: The callback to call, with a single
			dict argument when complete.
		"""
		callback(payload)

	def get_master(self):
		"""
		Get the address to the master host. This is designed for nodes
		to automatically contact the master without any other configuration.
		"""
		# TODO: SSL ?
		return "http://%s:%d" % (
			self.configuration.get_flat('master.host'),
			self.configuration.get_flat('master.port')
		)

	def get_endpoint(self):
		"""
		Get the endpoint - the URI on the remote end - for this request.
		You must override this in your subclass.
		"""
		# Override in your subclass to change the URI.
		raise NotImplementedError("You must implement get_endpoint().")

	def set_target(self, target):
		"""
		Set the target for this request. The target can be either:

		* A string, in the format http://hostname:port;
		* A node object.

		:arg str|Node target: The target for this request.
		"""
		if isinstance(target, basestring):
			self.target = target
		elif isinstance(target, paasmaker.model.Node):
			self.target = "http://%s:%d" % (target.route, target.apiport)
		else:
			raise ValueError("Target is not a string or Node object.")

	def process_response(self, response):
		"""
		Process the response before calling the callback.

		Some API requests can be self contained and do processing
		just after the request (see the node registration API request
		for an example).

		If you override this function, the user supplied callback
		will still be called with the original response, after this
		has completed and returned.
		"""
		# For overriding in your subclasses, if it's all self contained.
		# Note that the supplied callback, if provided, is called after this.
		pass

	def _authenticate_headers(self, headers):
		# Helper function to insert the right authentication headers,
		# if we're set to use those.
		if self.authmethod == 'tokenheader':
			headers['User-Token'] = self.authvalue
		if self.authmethod == 'superheader':
			headers['Super-Token'] = self.authvalue
		if self.authmethod == 'nodeheader':
			headers['Node-Token'] = self.authvalue

	def send(self, callback=None, **kwargs):
		"""
		Send the request to the remote server.

		Calls the callback when done, with an APIResponse object.
		The callback is called regardless of success; so you will
		need to check the supplied APIResponse object to see if
		the request succeeded.

		Any remaining keyword arguments are passed to the underlying
		Tornado HTTPRequest object, although some headers and other
		attributes are modified by this function to set up the
		appropriate authentication headers.

		:arg callback callback: The callback to call when done.
		"""
		if self.method == 'GET' and self.authmethod in ['node', 'super', 'token']:
			raise ValueError("Can't do a GET request with node, super, or token authentication methods.")

		logger.debug("In send() of API request of type %s", type(self))

		def payload_ready(payload):
			if self.method == 'POST':
				# Build what we're sending.
				data = {}
				data['data'] = payload
				data['auth'] = { 'method': self.authmethod, 'value': self.authvalue }

				encoded = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)

				kwargs['body'] = encoded
				# Always a POST, because we're sending a body.
				kwargs['method'] = 'POST'

				logger.debug("Payload sending to server: %s", encoded)
			else:
				kwargs['method'] = 'GET'

			# Don't follow redirects - this is an API request.
			kwargs['follow_redirects'] = False

			if not kwargs.has_key('headers'):
				kwargs['headers'] = {}

			self._authenticate_headers(kwargs['headers'])

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
			client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
			client.fetch(request, our_callback)

			# end of payload_ready()

		# Build the syncrhonous part of the payload.
		sync_payload = self.build_payload()

		# And then the async part.
		self.async_build_payload(sync_payload, payload_ready)

class StreamAPIWebsocketWrapper(paasmaker.thirdparty.twc.websocket.WebSocket):
	def configure(self, on_connected, on_message_handler, on_closed):
		self.connected = False
		self.on_connected = on_connected
		self.on_message_handler = on_message_handler
		self.on_closed = on_closed

	def on_open(self):
		self.connected = True
		self.on_connected(self)

	def on_close(self):
		self.connected = False
		self.on_closed(self)

	def send_message(self, message):
		self.write_message(json.dumps(message))

	def on_message(self, message):
		parsed = json.loads(message)
		self.on_message_handler(self, parsed)

class StreamAPIRequest(APIRequest):
	def __init__(self, *args):
		super(StreamAPIRequest, self).__init__(*args)

		self.stream_mode = 'websocket'
		self.active = True
		self.connected = False
		self.websocket = None
		self.message_callback = None
		self.error_callback = None
		self.send_queue = []
		self.session_id = None

	def set_stream_mode(self, mode):
		if mode not in ['websocket', 'longpoll']:
			raise ValueError("Invalid mode - try 'websocket' or 'longpoll'")

		self.stream_mode = mode

	def set_callbacks(self, message_callback, error_callback):
		self.message_callback = message_callback
		self.error_callback = error_callback

	def deactivate(self):
		self.active = False

	def send(self, *args, **kwargs):
		raise Exception("You should not use send() on StreamAPIRequest.")

	def send_message(self, request, body):
		logging.debug("Got message request %s, body %s", request, body)

		# Queue it up.
		self.send_queue.append((request, body))

		# And then really send it.
		self._real_send()

	def _format_request(self, message):
		complete_message = {
			'request': message[0],
			'data': message[1],
			'auth': {'method': self.authmethod, 'value': self.authvalue}
		}

		return complete_message

	def _real_send(self):
		if not self.connected:
			if self.stream_mode == 'websocket':
				logging.debug("Not connected, websocket mode.")
				# Connect to the websocket.
				# And then fallback if we can't.

				if not self.target:
					self.target = self.get_master()

				# Build and make the request.
				endpoint = self.target + self.get_endpoint()
				endpoint = endpoint.replace("http", "ws")

				logging.debug("Websocket endpoint: %s", endpoint)

				auth_headers = {}
				self._authenticate_headers(auth_headers)

				self.websocket = StreamAPIWebsocketWrapper(
					endpoint,
					io_loop=self.io_loop,
					extra_headers=auth_headers
				)
				self.websocket.configure(
					self._websocket_opened,
					self._websocket_incoming_message,
					self._websocket_closed
				)
				# TODO: Catch exception if this fails...
				logging.debug("Connecting...")
			else:
				# Just send along the current message queue.
				logging.debug("Not connected, long poll mode.")
				self._send_long_poll()
		else:
			# Connected, just use the existing backend.
			if self.stream_mode == 'websocket':
				logging.debug("Connected, websocket mode.")
				messages = self.send_queue
				self.send_queue = []
				for request in messages:
					complete_message = self._format_request(request)
					self.websocket.send_message(complete_message)
			else:
				# Use an out of band send-only request to get
				# the message to the server.
				logging.debug("Connected, long poll mode.")
				self._send_long_poll(send_only=True)

	def _send_long_poll(self, send_only=False):
		if not self.target:
			self.target = self.get_master()

		endpoint = self.target + '/websocket/longpoll?format=json'

		logging.debug("Commencing long poll. send_only=%s", send_only)
		logging.debug("Long poll endpoint: %s", endpoint)

		request_arguments = {}
		request_arguments['method'] = 'POST'
		request_arguments['headers'] = {}
		request_arguments['follow_redirects'] = False
		self._authenticate_headers(request_arguments['headers'])

		# TODO: Probably should remove the commands once we've confirmed
		# that the server has them.
		commands = self.send_queue
		self.send_queue = []

		formatted_commands = []
		for command in commands:
			formatted_commands.append(self._format_request(command))

		body = {}
		body['data'] = {
			'endpoint': self.get_endpoint(),
			'session_id': self.session_id,
			'commands': formatted_commands,
			'send_only': send_only
		}
		body['auth'] = {'method': self.authmethod, 'value': self.authvalue}
		request_arguments['body'] = json.dumps(body, cls=paasmaker.util.jsonencoder.JsonEncoder)

		def long_poll_result(response):
			if not send_only:
				self.connected = False

			if response.error:
				# Error.
				logger.error("Long Poll request failed with error: %s", response.error)
				if self.error_callback:
					self.error_callback(response.error)
			else:
				logger.debug("Raw Long Poll response body: %s", response.body)
				if response.body and response.body[0] == '{' and response.body[-1] == '}':
					try:
						parsed = json.loads(response.body)

						data = parsed['data']

						for message in data['messages']:
							if message.has_key('session_id'):
								self.session_id = message['session_id']
							else:
								if self.message_callback:
									self.message_callback(message)

						# NOTE: If you don't set a message callback, these messages
						# disappear into the ether.

						# And start polling again.
						if not send_only and self.active:
							logger.debug("Long poll is reconnecting...")
							self._send_long_poll()

					except ValueError, ex:
						logger.error("Unable to parse JSON:", exc_info=ex)
						if self.error_callback:
							self.error_callback("Unable to parse JSON: " + str(ex))
					except KeyError, ex:
						logger.error("Response was malformed:", exc_info=ex)
						if self.error_callback:
							self.error_callback("Response was malformed: " + str(ex))
				else:
					lgoger.error("Response was not JSON.")
					if self.error_callback:
						self.error_callback("Response was not JSON.")

		request = tornado.httpclient.HTTPRequest(endpoint, **request_arguments)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		if not send_only:
			self.connected = True
		client.fetch(request, long_poll_result)

	def _websocket_opened(self, client):
		logging.debug("Websocket opened.")
		self.connected = True
		# Clear the queue.
		self._real_send()

	def _websocket_incoming_message(self, client, message):
		logging.debug("Websocket incoming message - %s.", message)
		if self.message_callback:
			self.message_callback(message)

	def _websocket_closed(self, client, code, reason):
		logging.debug("Websocket closed - %s, %s.", code, reason)
		self.connected = False

# TODO: There are no unit tests here. It's expected that the other
# unit tests for API requests and controllers cover off the code in here.
# This is probably not the correct assumption, and these classes should
# be explicitly tested.

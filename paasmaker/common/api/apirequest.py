#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import json
import logging
import urlparse
import urllib

import paasmaker

import tornado

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
		self.protocol = 'http'
		if configuration:
			# By default, we assume that we're talking node->node
			self.authvalue = self.configuration.get_flat('node_token')
			self.io_loop = configuration.io_loop
		else:
			self.authvalue = None
			self.io_loop = tornado.ioloop.IOLoop.instance()

	def duplicate_auth(self, request):
		"""
		Duplicate the authentication details from the given request.
		Useful when doing subrequests internally.

		:arg APIRequest request: The request to copy the authentication
			details from.
		"""
		self.authvalue = request.authvalue
		self.target = request.target

	def set_https(self):
		"""
		Use SSL for the request.
		"""
		self.protocol = 'https'

	def set_auth(self, key):
		"""
		Set the authentication key presented to the server.
		It can be either a node token, super token, or user
		token, and the server will allow access depending on
		it's settings.

		:arg str key: The key to present to the server.
		"""
		self.authvalue = key

	def set_superkey_auth(self):
		"""
		Set this request to use super-key authentication.
		This will only work if a configuration object is
		set for this request. It's designed to be an easy
		way to set authentication for unit tests.
		"""
		if self.configuration is None:
			raise ValueError("No configuration object set.")

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
		return "%s://%s:%d" % (
			self.protocol,
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

		* A string, in the format "hostname:port" (http/https is prepended
		  automatically);
		* A node object.

		:arg str|Node target: The target for this request.
		"""
		if isinstance(target, basestring):
			self.target = "%s://%s" % (
				self.protocol,
				target
			)
		elif isinstance(target, paasmaker.model.Node):
			self.target = "%s://%s:%d" % (
				self.protocol,
				target.route,
				target.apiport
			)
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
		logger.debug("In send() of API request of type %s", type(self))

		def payload_ready(payload):
			if self.method == 'POST':
				# Build what we're sending.
				data = {}
				data['data'] = payload

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

			kwargs['headers']['Auth-Paasmaker'] = self.authvalue

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

class StreamAPIRequest(APIRequest):
	"""
	A base class for API requests that stream data from the remote end,
	by using the socket.io protocol.

	This superclass handles some authentication, queuing, and event handling.
	"""
	def __init__(self, *args, **kwargs):
		self.force_longpoll = False
		if 'force_longpoll' in kwargs:
			self.force_longpoll = kwargs['force_longpoll']
			del kwargs['force_longpoll']

		super(StreamAPIRequest, self).__init__(*args, **kwargs)

		self.remote_connected = False
		self.event_queue = []
		self.emit_queue = []
		self.error_callback = None

	def send(self, *args, **kwargs):
		raise Exception("You should not use send() on StreamAPIRequest.")

	def set_error_callback(self, error_callback):
		"""
		Set the callback to call on a connection or access denied error.

		The signature is as follows::

			def error(message):
				pass

		:arg callable error_callback: The callback, called with a single
			str argument, that indicates the error.
		"""
		self.error_callback = error_callback

	def connect(self):
		"""
		Establish a connection to the remote server. When it is connected,
		it will call the ``connected()`` function of this class, which can
		be overridden in your subclasses.

		If it is unable to connect, it will call the error callback that
		was set with ``set_error_callback()``.
		"""
		if not self.target:
			self.target = self.get_master()

		# Parse the URL - we need the hostname and port seperately.
		parsed = urlparse.urlparse(self.target)

		self.connection = paasmaker.thirdparty.socketioclient.SocketIO(
			parsed.hostname,
			parsed.port,
			io_loop=self.io_loop,
			query="auth=%s" % urllib.quote(self.authvalue),
			force_longpoll=self.force_longpoll,
			secure=(self.protocol == 'https')
		)

		# Hook up a few events to get started.
		self.connection.on('connect', self._connected)
		self.connection.on('connection_error', self._connection_error)
		self.connection.on('access_denied', self._access_denied)

		# And now connect. We'll be called back when it's ready.
		self.connection.connect()

	def _connection_error(self, response):
		if self.error_callback:
			self.error_callback(str(response.error))

	def _access_denied(self, message):
		if self.error_callback:
			self.error_callback(message)

	def on(self, *args):
		"""
		Hook up an event callback. Typically called as so::

			client.on('event.name', callback)

		If you call this before you call ``connect()``, it
		is queued and applied after the connection is established.
		"""
		if self.remote_connected:
			self.connection.on(*args)
		else:
			self.event_queue.append(args)

	def emit(self, *args):
		"""
		Emit an event to the remote end. Equivalent to ``emit()``
		in the JavaScript library.
		"""
		if self.remote_connected:
			self.connection.emit(*args)
		else:
			self.emit_queue.append(args)

	def _connected(self, socket):
		# Hook up all the events that we queued.
		for event in self.event_queue:
			self.connection.on(*event)
		self.event_queue = []

		# Send all emitted events that we queued.
		for event in self.emit_queue:
			self.connection.emit(*event)
		self.emit_queue = []

		# Mark us as connected.
		self.remote_connected = True
		self.connected(self.connection)

	def connected(self, socket):
		# Override in your subclasses to subscribe to events.
		pass

	def close(self):
		"""
		Close the connection to the remote server.
		"""
		if self.remote_connected:
			self.connection.disconnect()

# TODO: There are no unit tests here. It's expected that the other
# unit tests for API requests and controllers cover off the code in here.
# This is probably not the correct assumption, and these classes should
# be explicitly tested.

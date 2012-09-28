import tornado.web
import tornado.websocket
import tornado.escape
import logging
import paasmaker
import tornado.testing
import warnings
import os
import json
import time

import colander

# Types of API requests.
# 1. Node->Node. (ie, nodes talking to each other)
# 2. User->Pacemaker (cookie auth) (ie, AJAX browser callback)
# 3. User->Pacemaker (token auth) (ie, command line tool or other API request)

# Structure of API requests.
# auth: { method: 'node|cookie|token', value: 'token|cookie' }
# data: { ... keys ... }

class APIAuthRequestSchema(colander.MappingSchema):
	method = colander.SchemaNode(colander.String(),
		title="Method of authentication",
		description="One of node, cookie, or token")
	value = colander.SchemaNode(colander.String(),
		title="Authentication value",
		description="The authentication value")

class APIRequestSchema(colander.MappingSchema):
	auth = APIAuthRequestSchema()
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class BaseController(tornado.web.RequestHandler):
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2

	# You must override this in your subclass.
	auth_methods = []

	"""
	Base class for all controllers in the system.
	"""
	def initialize(self, configuration):
		self.configuration = configuration
		self.data = {}
		self.template = {}
		self.errors = []
		self.warnings = []
		self.format = 'html'
		self.root_data = {}
		self.session = None
		self.user = None
		self.auth = {}
		self.params = {}
		self.allowed_authentication_methods = ['anonymous']

	def prepare(self):
		self._set_format(self.get_argument('format', 'html'))

		# Unpack arguments into params.
		# TODO: Document why we're doing this.
		for k, v in self.request.arguments.iteritems():
			self.params[k] = v[-1]

		# If the post body is JSON, parse it and put it into the arguments.
		# TODO: This JSON detection is lightweight, but there might be corner
		# cases in it too...
		if self.request.method == 'POST' and self.request.body[0] == '{' and self.request.body[-1] == '}':
			parsed = json.loads(self.request.body)
			schema = APIRequestSchema()
			try:
				result = schema.deserialize(parsed)
			except colander.Invalid, ex:
				self.send_error(400, exc_info=ex)
				return
			self.auth = result['auth']
			self.params.update(result['data'])

		# Must be one of the supported auth methods.
		self.require_authentication(self.auth_methods)

	def param(self, name, default=None):
		if self.params.has_key(name):
			return self.params[name]
		else:
			return default

	def require_authentication(self, methods):
		if len(methods) == 0:
			# No methods provided.
			raise tornado.web.HTTPError(403, 'Access is denied. No authentication methods supplied.')

		found_allowed_method = False

		if self.ANONYMOUS in methods:
			# Anonymous is allowed. So let it go through...
			found_allowed_method = True

		if self.NODE in methods:
			# Check that a valid node authenticated.
			found_allowed_method = self.check_node_auth()

		if self.USER in methods:
			# Check that a valid user is authenticated.
			if self.get_current_user():
				found_allowed_method = True

		if not found_allowed_method:
			if self.format == 'json':
				raise tornado.web.HTTPError(403, 'Access is denied')
			else:
				# TODO: Don't hard code /login?
				self.redirect('/login?rt=' + tornado.escape.url_escape(self.request.uri))

	def check_node_auth(self):
		"""
		Check to see if the node authentication is valid.
		"""
		if self.auth.has_key('method') and self.auth['method'] == 'node':
			if self.auth.has_key('value') and self.auth['value'] == self.configuration.get_flat('auth_token'):
				return True
		return False

	def get_current_user(self):
		"""
		Get the currently logged in user.
		"""
		# Did we already look them up? Return that.
		if self.user:
			return self.user

		# Only pacemakers allow users to authenticate to them.
		if not self.configuration.is_pacemaker():
			return None

		# Fetch their cookie.
		raw = self.get_secure_cookie('user', max_age_days=self.configuration.get_flat('pacemaker.login_age'))
		if raw:
			# Lookup the user object.
			user = self.db().query(paasmaker.model.User).get(int(raw))
			# Make sure we have the user, and it's enabled and not deleted.
			if user and user.enabled and not user.deleted:
				self.user = user
				return user

		# Otherwise, return None.
		return None

	def add_data(self, key, name):
		self.data[key] = name

	def add_data_template(self, key, name):
		self.template[key] = name

	def add_error(self, error):
		self.errors.append(error)

	def add_warning(self, warning):
		self.warnings.append(warning)

	def db(self):
		if self.session:
			return self.session
		self.session = self.configuration.get_database_session()
		return self.session

	def _set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format

	def render(self, template, **kwargs):
		# Prepare our variables.
		if self.format == 'json':
			variables = {}
			variables.update(self.root_data)
			variables['data'] = self.data
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			self.set_header('Content-Type', 'application/json')
			self.write(json.dumps(variables, cls=paasmaker.util.jsonencoder.JsonEncoder))
		elif self.format == 'html':
			variables = self.data
			variables.update(self.root_data)
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			variables.update(self.template)
			variables.update(kwargs)
			super(BaseController, self).render(template, **variables)

	def write_error(self, status_code, **kwargs):
		# Reset the data queued up until now.
		self.data = {}
		self.root_data['error_code'] = status_code
		if kwargs.has_key('exc_info'):
			self.add_error('Exception: ' + str(kwargs['exc_info'][0]) + ': ' + str(kwargs['exc_info'][1]))
		self.render('error/error.html')

	def on_finish(self):
		self.application.log_request(self)

# A schema for websocket incoming messages, to keep them consistent.
class WebsocketMessageSchema(colander.MappingSchema):
	request = colander.SchemaNode(colander.String(),
		title="Request",
		description="What is intended from this request")
	sequence = colander.SchemaNode(colander.Integer(),
		title="Sequence",
		description="The sequence number for this request. Errors are returned matching this sequence, so you can tell which request they originated from. Optional",
		default=0,
		missing=0)
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))
	auth = APIAuthRequestSchema()

class BaseWebsocketHandler(tornado.websocket.WebSocketHandler):
	"""
	Base class for WebsocketHandlers.
	"""
	def initialize(self, configuration):
		self.configuration = configuration

	def parse_message(self, message):
		parsed = json.loads(message)
		schema = WebsocketMessageSchema()
		try:
			result = schema.deserialize(parsed)

			# Validate their authentication details.
			# Have to be authenticated for anything to work.
			# TODO: Implement!
		except colander.Invalid, ex:
			if not parsed.has_key('sequence'):
				parsed['sequence'] = -1
			self.send_error(str(ex), parsed)
			return None

		return result

	def validate_data(self, message, schema):
		try:
			result = schema.deserialize(message['data'])
		except colander.Invalid, ex:
			self.send_error(str(ex), message)
			return None

		return result

	def send_error(self, error, message):
		self.write_message(self.encode_message(self.make_error(error, message)))

	def send_success(self, typ, data):
		self.write_message(self.encode_message(self.make_success(typ, data)))

	def make_error(self, error, message):
		message = {
			'type': 'error',
			'data': { 'error': error, 'sequence': message['sequence'] }
		}
		return message

	def make_success(self, typ, data):
		message = {
			'type': typ,
			'data': data
		}
		return message

	def encode_message(self, message):
		return json.dumps(message, cls=paasmaker.util.jsonencoder.JsonEncoder)

class BaseControllerTest(tornado.testing.AsyncHTTPTestCase):
	config_modules = []

	def late_init_configuration(self):
		"""
		Late initialize configuration. This is to solve the chicken-and-egg issue of getting
		this unit tests test HTTP port.
		"""
		if not self.configuration:
			self.configuration = paasmaker.common.configuration.ConfigurationStub(port=self.get_http_port(), modules=self.config_modules)
		return self.configuration

	def setUp(self):
		self.configuration = None
		super(BaseControllerTest, self).setUp()
	def tearDown(self):
		self.configuration.cleanup()
		super(BaseControllerTest, self).tearDown()

	def fetch_user_auth(self, url, user, **kwargs):
		# Add a cookie header.
		# TODO: Figure out how to do this.
		request = tornado.httpclient.HTTPRequest(url, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.1, self.stop)
		self.wait()

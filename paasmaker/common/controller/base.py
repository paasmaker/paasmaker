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

from ..testhelpers import TestHelpers

# Types of API requests.
# 1. Node->Node. (ie, nodes talking to each other)
# 2. User->Pacemaker (cookie auth) (ie, AJAX browser callback)
# 3. User->Pacemaker (token auth) (ie, command line tool or other API request)

# Structure of API requests.
# auth: { method: 'node|cookie|token', value: 'token|cookie' }
# data: { ... keys ... }

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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
	SUPER = 3

	# You must override this in your subclass.
	AUTH_METHODS = []

	"""
	Base class for all controllers in the system.
	"""
	def initialize(self, configuration=None, io_loop=None):
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
		self.super_auth = False
		self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

		self.add_data_template('format_form_error', self.format_form_error)

	def prepare(self):
		self._set_format(self.get_argument('format', 'html'))

		# Unpack arguments into params.
		# TODO: Document why we're doing this.
		for k, v in self.request.arguments.iteritems():
			self.params[k] = v[-1]

		# If the post body is JSON, parse it and put it into the arguments.
		# TODO: This JSON detection is lightweight, but there might be corner
		# cases in it too...
		if self.request.method == 'POST' and len(self.request.body) > 0 and self.request.body[0] == '{' and self.request.body[-1] == '}':
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
		self.require_authentication(self.AUTH_METHODS)

	def validate_data(self, schema):
		"""
		Validate the request data with the given schema, returning
		an error if it doesn't match.
		"""
		try:
			result = schema.deserialize(self.params)
		except colander.Invalid, ex:
			logger.error("Invalid data supplied to this controller.")
			logger.error(self)
			logger.error(ex)
			self.send_error(400, exc_info=ex)

	def param(self, name, default=None):
		if self.params.has_key(name):
			return self.params[name]
		else:
			return default

	def redirect(self, target, **kwargs):
		if self.format == 'html':
			# Only actually redirect in HTML mode - we don't need to redirect API requests.
			super(BaseController, self).redirect(target, **kwargs)
		else:
			# TODO: Don't assume that the request is ready for rendering.
			self.render("api/apionly.html")
			self.finish()

	def require_authentication(self, methods):
		if len(methods) == 0:
			# No methods provided.
			raise tornado.web.HTTPError(403, 'Access is denied. No authentication methods supplied. This is a server side coding error.')

		found_allowed_method = False

		if self.ANONYMOUS in methods:
			# Anonymous is allowed. So let it go through...
			logger.debug("Anonymous method allowed. Allowing request.")
			found_allowed_method = True

		if self.NODE in methods:
			# Check that a valid node authenticated.
			logger.debug("Checking node authentication.")
			found_allowed_method = found_allowed_method or self.check_node_auth()
			logger.debug("Node authentication: %s", str(found_allowed_method))

		if self.SUPER in methods:
			# Check that a valid super key was supplied.
			logger.debug("Checking super authentication.")
			found_allowed_method = found_allowed_method or self.check_super_auth()
			if found_allowed_method:
				self.super_auth = True
			logger.debug("Super authentication: %s", str(found_allowed_method))

		if self.USER in methods:
			# Check that a valid user is authenticated.
			logger.debug("Checking user authentication.")
			if self.get_current_user():
				found_allowed_method = True
			logger.debug("Super authentication: %s", str(found_allowed_method))

		if not found_allowed_method:
			# YOU ... SHALL NOT ... PAAS!
			# (But with less bridge breaking.)
			logger.warning("Access denied for request.")
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
			if self.auth.has_key('value') and self.auth['value'] == self.configuration.get_flat('node_token'):
				return True
		return False

	def check_super_auth(self):
		"""
		Check to see if the super authentication is valid.
		"""
		if self.configuration.is_pacemaker() and self.configuration.get_flat('pacemaker.allow_supertoken'):
			if self.auth.has_key('method') and self.auth['method'] == 'super':
				if self.auth.has_key('value') and self.auth['value'] == self.configuration.get_flat('pacemaker.super_token'):
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

		# See if we're using token authentication.
		test_token = None
		auth_using_token = self.auth.has_key('method') and self.auth['method'] == 'token'
		if auth_using_token and self.auth.has_key('value'):
			test_token = self.auth['value']
		# TODO: In tests, the headers dict below was case sensitive.
		# Almost certainly a fail on my part...
		auth_using_header = self.request.headers.has_key('User-Token')
		if auth_using_header:
			test_token = self.request.headers['user-token']
		if auth_using_token or auth_using_header:
			if test_token:
				# Lookup the user object.
				user = self.db().query(paasmaker.model.User) \
					.filter(paasmaker.model.User.apikey==test_token).first()
				# Make sure we have the user, and it's enabled and not deleted.
				if user and user.enabled and not user.deleted:
					self.user = user
					return user

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

	def format_form_error(self, form, field):
		if form.has_errors(field):
			return '<ul class="error"><li>%s</li></ul>' % tornado.escape.xhtml_escape(form.get_first_error(field))
		else:
			return ''

	def add_error(self, error):
		self.errors.append(error)
	def add_errors(self, errors):
		self.errors.extend(errors)

	def add_warning(self, warning):
		self.warnings.append(warning)
	def add_warnings(self, warnings):
		self.warnings.extend(warnings)

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
		self.set_status(status_code)
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
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2

	# You must override this in your subclass.
	AUTH_METHODS = []

	def initialize(self, configuration):
		self.configuration = configuration
		self.authenticated = False

	def parse_message(self, message):
		parsed = json.loads(message)
		schema = WebsocketMessageSchema()
		try:
			result = schema.deserialize(parsed)

			# Validate their authentication details.
			# Only required the first time - every subsequent message
			# they'll be considered authenticated.
			if self.authenticated:
				return result
			else:
				self.check_authentication(result['auth'], result)
				if self.authenticated:
					return result
				else:
					return None
		except colander.Invalid, ex:
			if not parsed.has_key('sequence'):
				parsed['sequence'] = -1
			self.send_error(str(ex), parsed)
			return None

	def check_authentication(self, auth, message):
		if len(self.AUTH_METHODS) == 0:
			# No methods provided.
			self.send_error('Access is denied. No authentication methods supplied. This is a server side coding error.', message)
			return

		found_allowed_method = False

		if self.ANONYMOUS in self.AUTH_METHODS:
			# Anonymous is allowed. So let it go through...
			found_allowed_method = True

		if self.NODE in self.AUTH_METHODS:
			# Check that a valid node authenticated.
			if auth.has_key('method') and auth['method'] == 'node':
				if auth.has_key('value') and auth['value'] == self.configuration.get_flat('node_token'):
					found_allowed_method = True

		# TODO: Handle user token authentication.
		if not found_allowed_method:
			self.send_error('Access is denied. Authentication failed.', message)
		else:
			self.authenticated = True

	def validate_data(self, message, schema):
		try:
			result = schema.deserialize(message['data'])
		except colander.Invalid, ex:
			self.send_error(str(ex), message)
			return None

		return result

	def send_error(self, error, message):
		error_payload = self.make_error(error, message)
		error_message = self.encode_message(error_payload)
		self.write_message(error_message)

	def send_success(self, typ, data):
		self.write_message(self.encode_message(self.make_success(typ, data)))

	def make_error(self, error, message):
		result = {
			'type': 'error',
			'data': { 'error': error, 'sequence': message['sequence'] }
		}
		return result

	def make_success(self, typ, data):
		message = {
			'type': typ,
			'data': data
		}
		return message

	def encode_message(self, message):
		return json.dumps(message, cls=paasmaker.util.jsonencoder.JsonEncoder)

class BaseControllerTest(tornado.testing.AsyncHTTPTestCase, TestHelpers):

	config_modules = []

	def late_init_configuration(self, io_loop):
		"""
		Late initialize configuration. This is to solve the chicken-and-egg issue of getting
		this unit tests test HTTP port.
		"""
		if not self.configuration:
			self.configuration = paasmaker.common.configuration.ConfigurationStub(
				port=self.get_http_port(),
				modules=self.config_modules,
				io_loop=io_loop)
		return self.configuration

	def setUp(self):
		self.configuration = None
		super(BaseControllerTest, self).setUp()
		self.configuration.setup_job_watcher()
	def tearDown(self):
		self.configuration.cleanup()
		super(BaseControllerTest, self).tearDown()

	def fetch_with_user_auth(self, url, **kwargs):
		"""
		Fetch the given URL as a user, creating a user to authenticate as
		if needed.

		Calls self.stop when the request is ready, so your unit test should
		call self.wait() for the response.

		If URL contains '%d', this is replaced with the test HTTP port.
		Otherwise, the URL is untouched.
		"""
		# Create a test user - if required.
		s = self.configuration.get_database_session()
		user = s.query(paasmaker.model.User) \
				.filter(paasmaker.model.User.login=='username') \
				.first()

		if not user:
			# Not found. Make one.
			u = paasmaker.model.User()
			u.login = 'username'
			u.email = 'username@example.com'
			u.name = 'User Name'
			u.password = 'testtest'
			s.add(u)
			s.commit()
			s.refresh(u)

		# Ok, now that we've done that, try to log in.
		request = paasmaker.common.api.LoginAPIRequest(self.configuration)
		request.set_credentials('username', 'testtest')
		request.send(self.stop)
		response = self.wait()
		if not response.success:
			raise Exception('Failed to login as test user.')

		# Athenticate the next request.
		if not kwargs.has_key('headers'):
			kwargs['headers'] = {}
		kwargs['headers']['Cookie'] = 'user=' + response.data['token']

		# Add a cookie header.
		resolved_url = url
		if url.find('%d') > 0:
			resolved_url = resolved_url % self.get_http_port()
		request = tornado.httpclient.HTTPRequest(resolved_url, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

import logging
import warnings
import os
import json
import time
import datetime
import math
import uuid
import sys

import paasmaker
from ..testhelpers import TestHelpers
from ..core import constants

import tornado.testing
import tornado.web
import tornado.websocket
import tornado.escape
import colander
import sqlalchemy
from pubsub import pub

# Types of API requests.
# 1. Node->Node. (ie, nodes talking to each other)
# 2. User->Pacemaker (cookie auth) (ie, AJAX browser callback)
# 3. User->Pacemaker (token auth) (ie, command line tool or other API request)

# Structure of API requests.
# auth: 'value'
# data: { ... keys ... }

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class APIRequestSchema(colander.MappingSchema):
	auth = colander.SchemaNode(colander.String(), title="Auth value", missing="", default="")
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class BaseController(tornado.web.RequestHandler):
	"""
	Base controller class, that all other HTTP controllers should
	decend from.

	Provides the following services:

	* Access control, specifying what methods of authentication
	  are valid for the controller.
	* Input parsing, transparently converting standard form encoded
	  POST requests and JSON encoded POST requests in the same way.
	* Output transformations, returning either JSON or HTML as
	  requested.

	The ExampleController shows basic ways to use the base controller.
	"""
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2
	SUPER = 3

	# You must override this in your subclass.
	AUTH_METHODS = []

	# Shared permissions cache for all controllers.
	# Why no locking? We're relying on the Python GIL to sort
	# this out for us.
	PERMISSIONS_CACHE = {}

	def initialize(self, **kwargs):
		# This is defined here so controllers can change it per-request.
		self.DEFAULT_PAGE_SIZE = 10

		self.configuration = kwargs['configuration']
		self.data = {}
		self.template = {}
		self.errors = []
		self.warnings = []
		self.format = 'html'
		self.root_data = {}
		self.session = None
		self.user = None
		self.auth = ""
		self.params = {}
		self.raw_params = {}
		self.super_auth = False

		self.add_data_template('format_form_error', self.format_form_error)
		self.add_data_template('nice_state', self.nice_state)
		if self.configuration.is_pacemaker():
			self.add_data_template('frontend_domain_postfix', self.configuration.get_flat('pacemaker.frontend_domain_postfix'))

		# Add a header that is our node's UUID.
		uuid = self.configuration.get_node_uuid()
		if uuid:
			self.add_header('X-Paasmaker-Node', self.configuration.get_node_uuid())

	def prepare(self):
		"""
		Called to prepare the request, before the method that will
		handle the request itself.

		Performs several actions:

		* Parses and stores a JSON POST body if present.
		* Sets the format flag based on the query string.
		* Checks that the user is authenticated with a valid
		  authentication method, and terminates the request
		  with a 403 if it can't find a suitable method.
		"""
		self._set_format(self.get_argument('format', 'html'))

		if self.request.method == 'POST':
			# If the post body is JSON, parse it and put it into the arguments.
			# TODO: This JSON detection is lightweight, but there might be corner
			# cases in it too...
			if len(self.request.body) > 0 and self.request.body[0] == '{' and self.request.body[-1] == '}':
				parsed = json.loads(self.request.body)
				schema = APIRequestSchema()
				try:
					result = schema.deserialize(parsed)
				except colander.Invalid, ex:
					self.send_error(400, exc_info=ex)
					return
				self.auth = result['auth']
				self.raw_params.update(result['data'])

		# Unpack the request arguments into raw params.
		# This is so it behaves just like an API request as well.
		# We also unflatten it here, to make it into a data structure.
		# TODO: Properly unit test this.
		pairs = []
		for k, v in self.request.arguments.iteritems():
			for value in v:
				pairs.append((k, value))
		ftzr = paasmaker.util.flattenizr.Flattenizr()
		structure = ftzr.unflatten(pairs)
		# TODO: This could allow GET variables to replace POST variables...
		# TODO: This means GET variables can override values in the JSON structure.
		self.raw_params.update(structure)

		# Must be one of the supported auth methods.
		self._require_authentication(self.AUTH_METHODS)

	def validate_data(self, api_schema, html_schema=None):
		"""
		Validate the supplied POST data with the given schema.
		In the case of JSON requests, terminate the request immediately
		if the data is invalid. In the case of HTML requests,
		set a validation failed error message, and then
		return False - it's up to the caller to check this
		value and handle it as appropriate. The reason that HTML
		requests return False is that it then gives the controller
		the ability to redisplay the form with the users data in it,
		ready for another attempt.

		:arg SchemaNode api_schema: The API schema to validate against.
		:arg SchemaNode html_schema: The optional HTML schema to validate
			against. If not supplied, the API schema is used regardless of
			the request mode.
		"""
		# Select the real schema to use.
		schema = api_schema
		if self.format == 'html' and html_schema:
			schema = html_schema

		try:
			self.params.update(schema.deserialize(self.raw_params))
		except colander.Invalid, ex:
			logger.error("Invalid data supplied to this controller.")
			logger.error(ex)
			# Store and return the individual errors.
			self.add_data('input_errors', ex.asdict())
			if self.format == 'html':
				self.add_error("There was an error with the input.")
				# Now, copy in the data anyway - as this is the data
				# used to rebuild the forms if needed. The caller MUST
				# heed the fact that the data is invalid.
				self.params = self.raw_params
				return False
			else:
				self.add_error('Invalid data supplied.')
				# This will terminate the request, and also
				# in the returned body should be JSON with a
				# description of the errors.
				raise tornado.web.HTTPError(400, 'Invalid data supplied.')

		return True

	def redirect(self, target, **kwargs):
		"""
		Perform a redirect to the given target URL.

		If the request is a JSON formatted request, this immediately
		returns JSON and returns a 200 code, instead of a redirect.

		:arg str target: The target URI.
		"""
		if self.format == 'html':
			# Only actually redirect in HTML mode - we don't need to redirect API requests.
			super(BaseController, self).redirect(target, **kwargs)
		else:
			self.render("api/apionly.html")

	def _require_authentication(self, methods):
		"""
		Check the authentication methods until one is found that
		can be satisfied. In HTML mode, redirects to the login page.
		In JSON mode, it returns a 403 error and terminates the request.
		"""
		if len(methods) == 0:
			# No methods provided.
			raise tornado.web.HTTPError(403, 'Access is denied. No authentication methods supplied. This is a server side coding error.')

		found_allowed_method = False

		if self.ANONYMOUS in methods:
			# Anonymous is allowed. So let it go through...
			logger.debug("Anonymous method allowed. Allowing request.")
			found_allowed_method = True

		# See if the request has an auth value.
		auth_value = self.auth
		if 'Auth-Paasmaker' in self.request.headers:
			# User supplied an auth value via header;
			# check that value.
			auth_value = self.request.headers['Auth-Paasmaker']

		if len(auth_value) > 0:
			# We've been supplied a value. Now test it.
			if self.NODE in methods:
				if auth_value == self.configuration.get_flat('node_token'):
					# Permitted.
					logger.debug("Permitted node token authentication.")
					found_allowed_method = True

			if self.SUPER in methods and self.configuration.is_pacemaker() and self.configuration.get_flat('pacemaker.allow_supertoken'):
				if auth_value == self.configuration.get_flat('pacemaker.super_token'):
					# Permitted.
					logger.debug("Permitted super token authentication.")
					found_allowed_method = True
					self.super_auth = True

			if self.USER in methods and self.configuration.is_pacemaker():
				# If the used passed an API key, try to look that up.
				user = self.db().query(
					paasmaker.model.User
				).filter(
					paasmaker.model.User.apikey == auth_value
				).first()
				# Make sure we have the user, and it's enabled and not deleted.
				if user and user.enabled and not user.deleted:
					self.user = user
					self._update_user_permissions_cache()
					found_allowed_method = True
					logger.debug("Permitted user token authentication.")

		# Finally, if USER authentication is permitted, and
		# we're not authenticated yet, enforce that.
		if self.USER in methods and self.configuration.is_pacemaker() and not found_allowed_method:
			user = self.get_current_user()
			if user:
				found_allowed_method = True

		# And based on the result...
		if not found_allowed_method:
			# YOU ... SHALL NOT ... PAAS!
			# (But with less bridge breaking.)
			logger.warning("Access denied for request.")
			if self.format == 'json':
				raise tornado.web.HTTPError(403, 'Access is denied')
			else:
				self.redirect('/login?rt=' + tornado.escape.url_escape(self.request.uri))

	def get_current_user(self):
		"""
		Get the currently logged in user. Only tests for HTTP cookies
		to perform the login.
		"""
		# Did we already look them up? Return that.
		if self.user:
			return self.user

		# Only pacemakers allow users to authenticate to them.
		if not self.configuration.is_pacemaker():
			return None

		# Fetch their cookie.
		raw = self.get_secure_cookie(
			'user',
			max_age_days=self.configuration.get_flat('pacemaker.login_age')
		)
		if raw:
			# Lookup the user object.
			user = self.db().query(
				paasmaker.model.User
			).get(int(raw))
			# Make sure we have the user, and it's enabled and not deleted.
			if user and user.enabled and not user.deleted:
				self.user = user
				self._update_user_permissions_cache()

		return self.user

	def _update_user_permissions_cache(self):
		# Update their permissions cache. The idea is to do
		# one SQL query per request to check it, and 2 if
		# the permissions have changed - the second one is to
		# update the permissions.
		# TODO: The cache class is tested via the model unit tests,
		# but add a few more unit tests to make sure that this works properly.
		# TODO: Constrain the size of this cache.
		if self.user:
			user_key = str(self.user.id)
			if not self.PERMISSIONS_CACHE.has_key(user_key):
				self.PERMISSIONS_CACHE[user_key] = paasmaker.model.WorkspaceUserRoleFlatCache(self.user)
			self.PERMISSIONS_CACHE[user_key].check_cache(self.db())

	def has_permission(self, permission, workspace=None, user=None):
		"""
		Determine if the currently logged in user has the named
		permission. Returns True if they do, or False otherwise.

		:arg str permission: The permission to check for.
		:arg Workspace workspace: The optional workspace to limit
			the scope to.
		:arg User user: The optional user to compare for, rather
			than the logged in user.
		"""
		if not user and self.super_auth:
			# If authenticated with the super token,
			# you can do anything. With great power comes
			# great responsiblity...
			return True
		if not user:
			# No user supplied? Use the current user.
			user = self.get_current_user()
		if not user:
			# Still no user? Not logged in.
			# This situation should not occur, because the parent
			# controller is protected.
			raise tornado.web.HTTPError(403, "Not logged in.")

		# NOTE: Nodes are not checked to see if they have permission,
		# as they're only permitted to access a few controllers anyway.
		# They're assigned permission by being able to authenticate
		# to some controllers.

		allowed = self.PERMISSIONS_CACHE[str(user.id)].has_permission(
			permission,
			workspace
		)
		return allowed

	def require_permission(self, permission, workspace=None, user=None):
		"""
		Require the given permission to continue. Stops the request
		with a 403 if the user is not granted the given permission.

		:arg str permission: The permission to check for.
		:arg Workspace workspace: The optional workspace to limit the
			scope to.
		:arg User user: The optional user to check the permission for.
		"""
		allowed = self.has_permission(permission, workspace, user)
		if not allowed:
			self.add_error("You require permission %s to access." % permission)
			raise tornado.web.HTTPError(403, "Access denied.")

	def add_data(self, key, value):
		"""
		Add a named data key to this request, that will then appear
		in the output. If the request is JSON, it forms a key in the
		dict that is generated for it's output. If the request is HTML,
		then it is available in the template with the supplied name.

		If key already exists, it's value is overwritten.

		:arg str key: The name of the value.
		:arg object value: The value.
		"""
		self.data[key] = value

	def add_data_template(self, key, value):
		"""
		Add a named data key to this request. Keys added with this
		method will only be available to the template, and never returned
		to clients requesting via JSON. This allows you to add data for
		the template that might be privileged, which would be undesirable
		to add to the JSON output. Also, it can be used to add functions
		for use in templates, for which it would make no sense to return as
		JSON.
		"""
		self.template[key] = value

	def get_data(self, key):
		"""
		Get an existing data key previously added with ``add_data()``. Raises
		a ``KeyError`` if not found.
		"""
		return self.data[key]

	def get_data_template(self, key):
		"""
		Get an existing template data key previously added with
		``add_data_template()``. Raises a ``KeyError`` if not found.
		"""
		return self.template[key]

	def format_form_error(self, field):
		"""
		Helper function supplied to the templates that format errors
		for a named form field.

		Assumes that the data has an 'input_errors' key,
		that maps to a list of errors for that field.

		:arg str field: The field to display the errors for.
		"""
		if self.data.has_key('input_errors') and self.data['input_errors'].has_key(field):
			return '<ul class="error"><li>%s</li></ul>' % tornado.escape.xhtml_escape(self.data['input_errors'][field])
		else:
			return ''

	def nice_state(self, state):
		"""
		Helper function supplied to templates that formats a state
		string a little bit nicer. Basically, converts it to lower case
		and capitalizes only the first letter.

		:arg str state: The state to format.
		"""
		return state[0] + state[1:].lower()

	def add_error(self, error):
		"""
		Add an error to the request.

		:arg str error: The error message.
		"""
		self.errors.append(error)
	def add_errors(self, errors):
		"""
		Add several errors to the request.

		:arg list errors: The errors to add.
		"""
		self.errors.extend(errors)

	def add_warning(self, warning):
		"""
		Add a warning to this request.

		:arg str warning: The warning to add.
		"""
		self.warnings.append(warning)
	def add_warnings(self, warnings):
		"""
		Add several warnings to this request.

		:arg list warnings: The list of warnings to add.
		"""
		self.warnings.extend(warnings)

	def db(self):
		"""
		Fetch a SQLAlchemy database session.

		Each request returns only one Session object. If you call
		``db()`` several times during a request, each one will be
		the same Session object.
		"""
		if self.session:
			return self.session
		self.session = self.configuration.get_database_session()
		return self.session

	def _set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format

	def render(self, template, **kwargs):
		"""
		Render the response to the client, and finish the request.

		The template supplied is the name of the template file
		to use when in HTML mode. If the request is in JSON
		mode, the template is ignored and instead JSON is output to
		the client.
		"""
		# Prepare our variables.
		if self.format == 'json':
			variables = {}
			variables.update(self.root_data)
			variables['data'] = self.data
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			self.set_header('Content-Type', 'application/json')
			self.write(json.dumps(variables, cls=paasmaker.util.jsonencoder.JsonEncoder))
			# The super classes render() calls finish at this stage,
			# so we do so here.
			self.finish()
		elif self.format == 'html':
			variables = self.data
			variables.update(self.root_data)
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			variables.update(self.template)
			variables.update(kwargs)
			variables['PERMISSION'] = constants.PERMISSION
			variables['has_permission'] = self.has_permission
			super(BaseController, self).render(template, **variables)

	def write_error(self, status_code, **kwargs):
		"""
		Write an error and terminate the request. You can use this
		to finish your request early, although flow continues past
		this function.

		This renders an error template with error data. It discards
		all other data added with ``add_data()``.

		:arg int status_code: The HTTP status code to send.
		"""
		# Reset the data queued up until now.
		# Except for input_errors.
		if self.data.has_key('input_errors'):
			self.data = {'input_errors': self.data['input_errors']}
		else:
			self.data = {}
		self.root_data['error_code'] = status_code
		if kwargs.has_key('exc_info'):
			self.add_error('Exception: ' + str(kwargs['exc_info'][0]) + ': ' + str(kwargs['exc_info'][1]))
		self.set_status(status_code)
		self.render('error/error.html')

	def on_finish(self):
		self.application.log_request(self)

	def _get_router_stats_for(self, name, input_id, callback, output_key='router_stats', title=None):
		"""
		Helper function to get the aggregated router stats for
		the named aggregation group. Places the result automatically
		into the given output key, with the given title.

		:arg str name: The aggregation name.
		:arg int input_id: The aggregation input ID.
		:arg callable callback: The callback to call when it's done.
			It's single argument is the stats data.
		:arg str output_key: The output key name to insert the data
			as. If None, does not add the data at all, and only
			calls the callback with the data.
		:arg str title: The optional title to give this set of data.
		"""
		router_stats = paasmaker.router.stats.ApplicationStats(
			self.configuration
		)

		output = {
			'name': name,
			'input_id': input_id,
			'title': title,
			'data': None
		}

		if output_key:
			self.add_data(output_key, output)

		self.add_data_template('router_stats_display', paasmaker.router.stats.ApplicationStats.DISPLAY_SET)

		def got_router_stats(result):
			output['data'] = result
			callback(result)

		def router_stats_error(error, exception=None):
			self.add_warning('Unable to fetch router stats: ' + error)
			callback(None)

		def got_router_vtset(vtset):
			router_stats.total_for_list(
				'vt',
				vtset,
				got_router_stats,
				router_stats_error
			)

		def stats_system_ready():
			router_stats.vtset_for_name(
				name,
				input_id,
				got_router_vtset
			)

		router_stats.setup(
			stats_system_ready,
			router_stats_error
		)

	def _redirect_job(self, job_id, url):
		"""
		Helper function to redirect to the job detail page
		for the given job ID. The supplied URL is used as
		the return URL.

		:arg str job_id: The job ID to list for.
		:arg str url: The return URL shown on the detail page.
		"""
		self.redirect("/job/detail/%s?ret=%s" % (
				job_id,
				tornado.escape.url_escape(url)
			)
		)

	def _paginate(self, key, data, page_size=None):
		"""
		Simple paginator for lists of data.

		Using this is as simple as this::

			data = [1, 2, 3]
			self._paginate('data', data)

		In your templates, you can then include the pagination
		template, which will set up links for you to page
		between the data. In JSON requests, it will by default
		return all results. However, if you pass the ``pagesize``
		query parameter, it will paginate the data in pages
		of that size.

		This will read the query string parameter ``page`` to
		determine what page to show. For this reason, you'll
		only want to use one call to ``_paginate()`` per request
		handler.

		Your controller can change the default page size for
		by setting the class variable DEFAULT_PAGE_SIZE.

		The key that is added to the data has several sub
		keys, used to show information about the data.

		* total: The total number of entries.
		* pages: The total number of pages.
		* page: This page, starting at 1.
		* start: The first record number (starting at 1).
		* end: The last record number (ending at total).
		"""
		page = 1
		page_size = self.DEFAULT_PAGE_SIZE

		if self.raw_params.has_key('page'):
			try:
				page = int(self.raw_params['page'])
			except ValueError, ex:
				# Invalid, ignore.
				pass
		if self.raw_params.has_key('pagesize'):
			try:
				page_size = int(self.raw_params['pagesize'])
			except ValueError, ex:
				# Invalid, ignore.
				pass

		if isinstance(data, sqlalchemy.orm.query.Query):
			total = data.count()
		else:
			total = len(data)

		# For JSON requests, by default, don't paginate, as
		# this would be very confusing.
		# If the JSON request supplies a pagesize, then we
		# will start paginating.
		if self.format != 'html' and not self.raw_params.has_key('pagesize'):
			page_size = total

		pages = 0
		if total > 0:
			pages = int(math.ceil(float(total) / float(page_size)))
		start = (page - 1) * page_size
		end = min(page * page_size, total)

		page_data = {
			'total': total,
			'pages': pages,
			'page': page,
			'start': start + 1,
			'end': end
		}
		self.add_data('%s_pagination' % key, page_data)
		self.add_data(key, data[start:end])

	def _allow_user(self, user):
		self.set_secure_cookie("user", unicode("%d" % user.id))
		self.add_data('success', True)
		# Token is not for use with the auth token authentication method - because
		# it expires. Instead, it's supplied back as a cookie and in the data for
		# unit tests or other short lived systems.
		self.add_data('token', self.create_signed_value('user', unicode(user.id)))

class BaseLongpollController(BaseController):
	"""
	A base controller for long-poll controllers.

	The idea of long poll controllers is to wait for a while for information
	to return to clients. We should be sending back data since the last
	update, and then anything new.

	To implement, subclass this class, and implement the poll() method.
	You can also implement the poll_ended() method to send back a message
	if the timeout expires.

	You can use send_message() to queue up a few messages to go back,
	if a few changes have occurred since the last poll - which makes
	it a bit easier for your client side code to implement.

	The default long poll timeout is 20 seconds, which is designed to be
	inside the proxy's timeout.

	You should not override get() and post() in these controllers.
	"""
	LONGPOLL_MAX_TIME = 20 # 20 seconds. TODO: Make this configurable.

	@tornado.web.asynchronous
	def get(self, *args, **kwargs):
		# TODO: Detect when the connection is closed by the browser's end.
		# This is to cleanup any resources (such as pubsub subscriptions)

		# First thing we do is to set up a timeout to return a response.
		self._longpoll_timer = self.configuration.io_loop.add_timeout(
			time.time() + self.LONGPOLL_MAX_TIME,
			self._longpoll_expire
		)

		# Force the format to be JSON.
		self._set_format('json')

		# Somewhere to store the messages.
		self._messages = []

		# Now allow the subclass to take over.
		self.poll(*args, **kwargs)

	def post(self, *args, **kwargs):
		# Do the same thing as get(). The reason we implement
		# this is because the request might contain a POST body
		# with instructions on what to do.
		self.get(*args, **kwargs)

	def poll(self, *args, **kwargs):
		"""
		Override this in your subclass. Set up any listeners you
		need, and then when a message comes in, call ``send_message()``
		with a dict containing the message contents. By default,
		``send_message()`` then ends the request.
		"""
		raise NotImplementedError("You should implement poll().")

	def cleanup(self, callback, timeout_expired):
		"""
		Optionally override this in your subclass. This is called when
		the timeout has expired and we're about to return a response to
		the client. Call the callback when you're cleaned up and ready
		for the request to end. You can queue messages in here if you
		like, but be sure to pass ``queue=True`` to ``send_message()``.

		:arg callable callback: Callback to call when you're done.
		:arg bool timeout_expired: If True, the long poll timed out. Otherwise,
			it finished because the user requested it.
		"""
		callback()

	def send_message(self, message, queue=False):
		"""
		Send a message back to the client. This will end the request
		if queue is False. Otherwise, you can call it a few times to
		gather a few changes for the client.

		:arg dict message: The message body to return.
		:arg bool queue: If True, queues the message. Otherise,
			it ends the request.
		"""
		# Call this to send a message.
		self._messages.append(message)

		if not queue:
			self._finish_request(False)

	def _longpoll_expire(self):
		self._longpoll_timer = None
		self._finish_request(True)

	def _finish_request(self, timeout_expired):
		logger.debug("Finishing longpoll request.")
		if self._longpoll_timer:
			self.configuration.io_loop.remove_timeout(self._longpoll_timer)

		def finish():
			self.add_data('messages', self._messages)
			self.render('api/apionly.html')

		# Call the cleanup.
		self.cleanup(finish, timeout_expired)

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
	auth = colander.SchemaNode(colander.String(), title="Auth value", missing="", default="")

class BaseWebsocketHandler(tornado.websocket.WebSocketHandler):
	"""
	Base class for WebsocketHandlers.

	This base class handles authentication, parsing incoming messages,
	and sending back messages and errors.
	"""
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2
	SUPER = 3

	# You must override this in your subclass.
	AUTH_METHODS = []

	def initialize(self, configuration):
		"""
		Called by Tornado when the connection is established.
		"""
		self.configuration = configuration
		self.authenticated = False

	def parse_message(self, message):
		"""
		Helper function to parse a message. This function
		only validates it against the full schema, and then
		attempts to check the user's authentication. If the
		authentication fails or the message headers do not
		validate, an error is sent back to the client.

		Otherwise, the parsed message is returned.

		:arg str message: The raw message from the client.
		"""
		parsed = json.loads(message)
		schema = WebsocketMessageSchema()

		# See if there was a user cookie passed. If so, it's valid.
		# TODO: Permissions.
		# TODO: If this is not a pacemaker, handle that properly.
		raw = self.get_secure_cookie('user', max_age_days=self.configuration.get_flat('pacemaker.login_age'))
		if raw:
			# Lookup the user object.
			# TODO: This uses up a database session?
			user = self.configuration.get_database_session().query(
				paasmaker.model.User
			).get(int(raw))
			# Make sure we have the user, and it's enabled and not deleted.
			if user and user.enabled and not user.deleted:
				self.user = user
				self.authenticated = True

		try:
			result = schema.deserialize(parsed)

			# Validate their authentication details.
			# Only required the first time - every subsequent message
			# they'll be considered authenticated.
			if self.authenticated:
				return result
			else:
				self._check_authentication(result['auth'], result)
				if self.authenticated:
					return result
				else:
					return None
		except colander.Invalid, ex:
			if not parsed.has_key('sequence'):
				parsed['sequence'] = -1
			self.send_error(str(ex), parsed)
			return None

	def _check_authentication(self, auth_value, message):
		"""
		Check the authentication of the message. This is called
		by ``parse_message()``.
		"""
		if len(self.AUTH_METHODS) == 0:
			# No methods provided.
			self.send_error('Access is denied. No authentication methods supplied. This is a server side coding error.', message)
			return

		found_allowed_method = False

		if self.ANONYMOUS in self.AUTH_METHODS:
			# Anonymous is allowed. So let it go through...
			logger.debug("Anonymous method allowed. Allowing request.")
			found_allowed_method = True

		# See if the request has an auth value.
		if 'Auth-Paasmaker' in self.request.headers:
			# User supplied an auth value via header;
			# check that value.
			auth_value = self.request.headers['Auth-Paasmaker']

		if len(auth_value) > 0:
			# We've been supplied a value. Now test it.
			if self.NODE in self.AUTH_METHODS:
				if auth_value == self.configuration.get_flat('node_token'):
					# Permitted.
					logger.debug("Permitted node token authentication.")
					found_allowed_method = True

			if self.SUPER in self.AUTH_METHODS and self.configuration.is_pacemaker() and self.configuration.get_flat('pacemaker.allow_supertoken'):
				if auth_value == self.configuration.get_flat('pacemaker.super_token'):
					# Permitted.
					logger.debug("Permitted super token authentication.")
					found_allowed_method = True

			if self.USER in self.AUTH_METHODS and self.configuration.is_pacemaker():
				# If the used passed an API key, try to look that up.
				session = self.configuration.get_database_session()
				user = session.query(
					paasmaker.model.User
				).filter(
					paasmaker.model.User.apikey == auth_value
				).first()
				session.close()
				# Make sure we have the user, and it's enabled and not deleted.
				if user and user.enabled and not user.deleted:
					self.user = user
					found_allowed_method = True
					logger.debug("Permitted user token authentication.")

		# And based on the result...
		if not found_allowed_method:
			self.send_error('Access is denied. Authentication failed.', message)
		else:
			self.authenticated = True

	def validate_data(self, message, schema):
		"""
		Validate parsed data with the given schema. If this
		succeeds, the resulting deserialized data is returned.
		If it fails, an error is sent back to the client
		and None is returned.

		:arg dict message: The message body.
		:arg SchemaNode schema: The colander schema to validate
			against.
		"""
		try:
			result = schema.deserialize(message['data'])
		except colander.Invalid, ex:
			self.send_error(str(ex), message)
			return None

		return result

	def send_error(self, error, message):
		"""
		Send an error back to the client, framing it
		with the sequence number from the original message.

		:arg str error: The error message.
		:arg dict message: The parsed original message body.
		"""
		error_payload = self.make_error(error, message)
		error_message = self.encode_message(error_payload)
		self.write_message(error_message)

	def send_success(self, typ, data):
		"""
		Send a successful response to the client, handling
		encoding and framing.

		:arg str typ: The type of the message returned.
		:arg dict data: The data to return to the client.
		"""
		self.write_message(self.encode_message(self.make_success(typ, data)))

	def make_error(self, error, message):
		"""
		Helper function to build an error frame.
		"""
		result = {
			'type': 'error',
			'data': { 'error': error, 'sequence': message['sequence'] }
		}
		return result

	def make_success(self, typ, data):
		"""
		Helper function to build a successful data frame.
		"""
		message = {
			'type': typ,
			'data': data
		}
		return message

	def encode_message(self, message):
		"""
		Helper function to encode a message.
		"""
		return json.dumps(message, cls=paasmaker.util.jsonencoder.JsonEncoder)

class CommandSchema(colander.MappingSchema):
	pass

class CommandsSchema(colander.SequenceSchema):
	commands = CommandSchema(unknown='preserve')

class WebsocketLongpollWrapperSchema(colander.MappingSchema):
	endpoint = colander.SchemaNode(
		colander.String(),
		title="Websocket endpoint",
		description="The Websocket endpoint on the server side (the URI, eg /log/stream)"
	)
	session_id = colander.SchemaNode(
		colander.String(),
		title="Long poll session ID",
		description="The long poll session ID to resume. If not supplied, it will create a new session.",
		default=None,
		missing=None
	)
	# commands = colander.SchemaNode(
	# 	CommandsSchema(),
	# 	title="Commands",
	# 	description="List of commands to send to the websocket handler.",
	# 	default=[],
	# 	missing=[]
	# )
	send_only = colander.SchemaNode(
		colander.Boolean(),
		title="Send data only",
		description="Send data to the server only, do not return any messages.",
		default=False,
		missing=False
	)

class WebsocketWrapperClient(paasmaker.thirdparty.twc.websocket.WebSocket):
	def configure(self, configuration, on_connected, on_message_handler, on_closed):
		self.configuration = configuration
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

class WebsocketLongpollSessionmanager(object):
	def __init__(self):
		self.sessions = {}

	def has(self, session_id):
		if self.sessions.has_key(session_id):
			return True
		else:
			return False

	def create(self, endpoint, connected_callback, source_request):
		session_id = str(uuid.uuid4())

		def connected(client):
			# Call the connected callback to indicate that we're
			# connected.
			connected_callback(session_id)

		def closed(client):
			# Remove the session.
			if self.sessions.has_key(session_id):
				del self.sessions[session_id]

		def message(client, message):
			# Store the message in the sessions list.
			self.sessions[session_id]['messages'].append(message)

			# And publish that we have a new message.
			pub.sendMessage('websocketwrapper.message', session_id=session_id)

		extra_headers = {}
		if 'Auth-Paasmaker' in source_request.headers:
			extra_headers['Auth-Paasmaker'] = source_request.headers['Auth-Paasmaker']

		# Create the remote.
		remote_url = "ws://localhost:%d%s" % (self.configuration.get_flat('http_port'), endpoint)
		remote = WebsocketWrapperClient(
			remote_url,
			io_loop=self.configuration.io_loop,
			extra_headers=extra_headers
		)
		remote.configure(
			self.configuration,
			connected,
			message,
			closed
		)

		# Record the new session.
		self.sessions[session_id] = {
			'endpoint': endpoint,
			'remote': remote,
			'timeout': None,
			'messages': []
		}

		# Wait for callback.
		# The callback will kick everything else off.

	def send(self, session_id, message):
		if not self.sessions.has_key(session_id):
			raise ValueError("No such session %s" % session_id)

		self.sessions[session_id]['remote'].send_message(message)

	def messages_waiting(self, session_id):
		if not self.sessions.has_key(session_id):
			raise ValueError("No such session %s" % session_id)

		return len(self.sessions[session_id]['messages']) > 0

	def get_messages(self, session_id):
		if not self.sessions.has_key(session_id):
			raise ValueError("No such session %s" % session_id)

		# Get the messages, clearing them in the same process.
		messages = self.sessions[session_id]['messages']
		self.sessions[session_id]['messages'] = []
		return messages

	def touch(self, session_id):
		# "Touch" the session, adding a timeout to clean it up
		# in 60 seconds, or reset that timeout on an existing session.

		# TODO: It's probably not efficient to keep adding these callbacks,
		# as it's up to Python to clean them up when they're not referenced.
		# We should fix this. The reason it's done this way as a closure is because
		# you can't pass args to the add_timeout callback.
		def clean_session():
			# Close the session.
			session_data = self.sessions[session_id]
			del self.sessions[session_id]
			session_data['remote'].close()

		# Remove the existing cleanup timeout.
		if self.sessions[session_id]['timeout']:
			self.configuration.io_loop.remove_timeout(self.SESSIONS[self.session]['timeout'])

		# And add a new timeout to clean up this session.
		self.configuration.io_loop.add_timeout(datetime.timedelta(seconds=60), clean_session)

class WebsocketLongpollWrapper(BaseLongpollController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	# Theory of operation.
	# - You request this with several values: endpoint URL, and an array of commands.
	# - Server creates a 'session', which uses the websocket to connect to itself.
	# - Server processes all requests in that session, sends back the results.
	# - Whilst the client is disconnected, messages queue up.
	# - You get supplied a session ID. Use this when you call back to get things
	#   that have changed since last time. If nothing has changed, it waits until
	#   something does change, or until the timeout.
	# - If you don't come back in 60 seconds, your session gets dropped on the server
	#   side. If you come back with a dropped session ID, you get a message to indicate
	#   that, as you'd have to resubscribe again.
	# - Replies to the client are:
	#   {'error': 'error message'} (Normally no such session)
	#   {'messages': [{}, {}, ...]} (A list of messages since last time)
	#   {'session_id': '<session id>'} (The session ID to use next time).

	SESSIONS = WebsocketLongpollSessionmanager()

	def poll(self, *args, **kwargs):
		self.SESSIONS.configuration = self.configuration

		self.validate_data(WebsocketLongpollWrapperSchema())

		# The key 'commands' isn't correctly validating with Colander.
		# TODO: Fix this.
		if not self.raw_params.has_key('commands') or not isinstance(self.raw_params['commands'], list):
			raise tornado.web.HTTPError(400, "No commands key sent.")

		# Do we have an existing session?
		if self.params['session_id']:
			if self.SESSIONS.has(self.params['session_id']):
				# Resume that session.
				self._startup_session(self.params['session_id'], new_session=False)
				return
			else:
				# Asked for a session that didn't exist.
				raise tornado.web.HTTPError(400, "Session closed or non existent.")
		else:
			# Create a new session.
			self.SESSIONS.create(self.params['endpoint'], self._startup_session, self.request)

	def _startup_session(self, session_id, new_session=True):
		# Save the session ID for other callbacks.
		self.session_id = session_id
		# Touch the session, to create or reset the timeout.
		self.SESSIONS.touch(self.session_id)

		# Now send through all the commands.
		for command in self.raw_params['commands']:
			self.SESSIONS.send(self.session_id, command)

		if self.params['send_only'] or new_session:
			# End the request now - don't wait for messages.
			# Also end if it's a new session, so the remote has the session ID.
			self._finish_request(False)
		else:
			# Move onto the next phase, where we wait for messages to come back.
			self._await_messages()

	def _await_messages(self):
		# Do we have any messages pending?
		if self.SESSIONS.messages_waiting(self.session_id):
			# Send all those back now and then return.
			self._send_pending_messages()
		else:
			# No - so now let's wait for messages.
			pub.subscribe(self._on_pub_message, 'websocketwrapper.message')

	def _on_pub_message(self, session_id):
		# Send that message back, and terminate the request.
		pub.unsubscribe(self._on_pub_message, 'websocketwrapper.message')
		self.configuration.io_loop.add_callback(self._send_pending_messages)

	def _send_pending_messages(self):
		messages = self.SESSIONS.get_messages(self.session_id)
		for message in messages:
			self.send_message(message, queue=True)

		# And complete the request now.
		self._finish_request(False)

	def cleanup(self, callback, timeout_expired):
		if timeout_expired:
			# Unsubscribe before returning.
			pub.unsubscribe(self._on_pub_message, 'websocketwrapper.message')

		# Make sure to return the session ID.
		if hasattr(self, 'session_id'):
			self.send_message({'session_id': self.session_id}, queue=True)

		# Continue on as we were.
		callback()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/websocket/longpoll", WebsocketLongpollWrapper, configuration))
		return routes

##
## TEST CODE
##

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
		self._port = None
		self.test_port_allocator = paasmaker.util.port.FreePortFinder()

		super(BaseControllerTest, self).setUp()
		self.configuration.setup_job_watcher()

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseControllerTest, self).tearDown()

	def get_http_port(self):
		"""Returns the port used by the server.

		A new port is chosen for each test.
		"""
		if self._port is None:
			self._port = self.test_port_allocator.free_in_range(10100, 10199)
		return self._port

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

			# Allow them to do anything.
			# TODO: This makes for a poor test.
			r = paasmaker.model.Role()
			r.name = 'Test'
			r.permissions = paasmaker.common.core.constants.PERMISSION.ALL
			s.add(r)

			a = paasmaker.model.WorkspaceUserRole()
			a.user = u
			a.role = r

			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(s)
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

class BaseLongpollControllerTest(BaseControllerTest):
	def setUp(self):
		super(BaseLongpollControllerTest, self).setUp()

		# Turn down the long poll timeout to half a second.
		BaseLongpollController.LONGPOLL_MAX_TIME = 0.5

import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import colander

class ProfileUserDataSchema(colander.MappingSchema):
	userdata = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User Data",
		description="The user data to store.")

class ProfileController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		# No permissions check - you can only fetch your API key.
		# Note - we're allowing the API key here because only the logged in
		# user can view their own API key. So not a security risk.
		user = self.get_current_user()
		self.add_data('apikey', user.apikey)
		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile", ProfileController, configuration))
		return routes

class ProfileUserdataController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		# No permissions check - you can only fetch your userdata.
		user = self.get_current_user()
		self.add_data('userdata', user.userdata)
		self.render("api/apionly.html")

	def post(self):
		# Validate immediately.
		valid_data = self.validate_data(ProfileUserDataSchema())

		if not valid_data:
			# To handle a HTML request against this controller.
			raise tornado.web.HTTPError(400, "Invalid request.")

		# Don't check permissions, because you have to be authenticated,
		# and you only operate on your user's data anyway.
		user_stub = self.get_current_user()
		user = self.session.query(
			paasmaker.model.User
		).get(user_stub.id)

		user.userdata = self.params['userdata']

		self.session.add(user)
		self.session.commit()

		self.add_data('success', True)

		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile/userdata", ProfileUserdataController, configuration))
		return routes

class ProfileResetAPIKeyController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def post(self):
		user = self.get_current_user()
		user.generate_api_key()
		self.session.add(user)
		self.session.commit()

		self.add_data('apikey', user.apikey)
		self.redirect("/profile")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile/reset-api-key", ProfileResetAPIKeyController, configuration))
		return routes

class MyPermissionsController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self, mode):
		# TODO: This relies on a lot of assumptions
		# about the BaseController and the Permissions cache
		# class.
		user = self.get_current_user()
		cache = self.PERMISSIONS_CACHE[str(user.id)]

		self.add_data('version', cache.cache_version)
		self.add_data('permissions', cache.cache)

		if mode == '':
			# Normal JSON mode.
			self.render("api/apionly.html")
		else:
			# Emit a .js file.
			self.set_header('Content-Type', 'text/javascript')
			self.write("var currentUserPermissions = %s;" % json.dumps(cache.cache))
			self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/my-permissions(|.js)", MyPermissionsController, configuration))
		return routes

class ProfileControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ProfileController.get_routes({'configuration': self.configuration})
		routes.extend(ProfileUserdataController.get_routes({'configuration': self.configuration}))
		routes.extend(ProfileResetAPIKeyController.get_routes({'configuration': self.configuration}))
		routes.extend(MyPermissionsController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_profile(self):
		request = self.fetch_with_user_auth('http://localhost:%d/profile')
		response = self.wait()

		self.failIf(response.error)

		# Fetch the user that this matches.
		self.configuration.get_database_session(self.stop, None)
		s = self.wait()
		user = s.query(
			paasmaker.model.User
		).filter(
			paasmaker.model.User.login == 'username'
		).first()

		self.assertIn(user.apikey, response.body, "API key not present in body.")

	def test_userdata(self):
		request = self.fetch_with_user_auth('http://localhost:%d/profile/userdata?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertTrue('userdata' in response.body, "Userdata not returned.")

		# Set some user data.
		request = self.fetch_with_user_auth(
			'http://localhost:%d/profile/userdata?format=json',
			method='POST',
			body=json.dumps({'data': {'userdata': {'one': 'two'}}})
		)
		response = self.wait()

		self.failIf(response.error)
		self.assertTrue('success' in response.body, "Userdata not saved.")

		# Get the user data back.
		request = self.fetch_with_user_auth('http://localhost:%d/profile/userdata?format=json')
		response = self.wait()

		self.failIf(response.error)
		self.assertTrue('two' in response.body, "Userdata not returned.")

	def test_reset_apikey(self):
		request = self.fetch_with_user_auth('http://localhost:%d/profile?format=json')
		response = self.wait()

		self.failIf(response.error)

		# Fetch the user that this matches.
		self.configuration.get_database_session(self.stop, None)
		s = self.wait()
		user = s.query(
			paasmaker.model.User
		).filter(
			paasmaker.model.User.login == 'username'
		).first()

		self.assertIn(user.apikey, response.body, "API key not present in body.")

		# Parse out the API key.
		parsed = json.loads(response.body)
		key = parsed['data']['apikey']

		# Change the key.
		request = self.fetch_with_user_auth('http://localhost:%d/profile/reset-api-key', method='POST', body="format=json")
		response = self.wait()
		self.failIf(response.error)

		# Get the key that was returned.
		parsed = json.loads(response.body)
		changed_key = parsed['data']['apikey']

		self.assertNotEquals(key, changed_key, "Key was not changed.")

		# Now re-request the key. It should match what was returned.
		request = self.fetch_with_user_auth('http://localhost:%d/profile?format=json')
		response = self.wait()

		self.failIf(response.error)

		parsed = json.loads(response.body)

		self.assertNotEquals(key, parsed['data']['apikey'], "Key was not changed")
		self.assertEquals(changed_key, parsed['data']['apikey'], "Key was not stored correctly.")

	def test_my_permissions(self):
		request = self.fetch_with_user_auth('http://localhost:%d/my-permissions?format=json')
		response = self.wait()

		self.failIf(response.error)

		parsed = json.loads(response.body)

		self.assertTrue('data' in parsed, "Missing data section.")
		data = parsed['data']
		self.assertTrue('permissions' in data, "Missing permissions.")
		self.assertTrue('version' in data, "Missing permissions version.")

		request = self.fetch_with_user_auth('http://localhost:%d/my-permissions.js')
		response = self.wait()

		self.failIf(response.error)

		self.assertTrue("var currentUserPermissions =" in response.body)
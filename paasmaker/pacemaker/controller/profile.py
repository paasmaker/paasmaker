
import paasmaker
import tornado
import json
from paasmaker.common.controller import BaseController, BaseControllerTest

class ProfileController(BaseController):
	auth_methods = [BaseController.USER]

	def get(self):
		# TODO: Permissions.
		# Note - we're allowing the API key here because only the logged in
		# user can view their own API key. So not a security risk.
		self.add_data('apikey', self.get_current_user().apikey)
		self.render("user/profile.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile", ProfileController, configuration))
		return routes

class ProfileResetAPIKeyController(BaseController):
	auth_methods = [BaseController.USER]

	def post(self):
		user = self.get_current_user()
		user.generate_api_key()
		session = self.db()
		session.add(user)
		session.commit()

		self.add_data('apikey', user.apikey)
		self.redirect("/profile")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile/reset-api-key", ProfileResetAPIKeyController, configuration))
		return routes

class ProfileControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ProfileController.get_routes({'configuration': self.configuration})
		routes.extend(ProfileResetAPIKeyController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_profile(self):
		request = self.fetch_with_user_auth('http://localhost:%d/profile')
		response = self.wait()

		self.failIf(response.error)

		# Fetch the user that this matches.
		s = self.configuration.get_database_session()
		user = s.query(paasmaker.model.User) \
				.filter(paasmaker.model.User.login=='username') \
				.first()

		self.assertIn(user.apikey, response.body, "API key not present in body.")

	def test_reset_apikey(self):
		request = self.fetch_with_user_auth('http://localhost:%d/profile?format=json')
		response = self.wait()

		self.failIf(response.error)

		# Fetch the user that this matches.
		s = self.configuration.get_database_session()
		user = s.query(paasmaker.model.User) \
				.filter(paasmaker.model.User.login=='username') \
				.first()

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

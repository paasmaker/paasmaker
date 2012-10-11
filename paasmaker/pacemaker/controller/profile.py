
import paasmaker
import tornado
from paasmaker.common.controller import BaseController, BaseControllerTest

class ProfileController(BaseController):
	auth_methods = [BaseController.USER]

	def get(self):
		self.render("user/profile.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile", ProfileController, configuration))
		return routes

class ProfileControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration()
		routes = ProfileController.get_routes({'configuration': self.configuration})
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
				.filter(paasmaker.model.User.login=='danielf') \
				.first()

		print response.body
		self.assertIn(user.apikey, response.body, "API key not present in body.")
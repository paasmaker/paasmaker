
import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class ProfileController(BaseController):
	auth_methods = [BaseController.USER]

	def get(self):
		self.render("user/profile.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/profile", ProfileController, configuration))
		return routes


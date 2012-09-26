
import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class IndexController(BaseController):
	auth_methods = [BaseController.ANONYMOUS]

	def get(self):
		self.render("index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", IndexController, configuration))
		return routes



import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class IndexController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		if self.configuration.is_pacemaker():
			self.render("index.html")
		else:
			self.render("index-notpacemaker.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", IndexController, configuration))
		return routes


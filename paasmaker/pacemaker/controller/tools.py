
import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class ToolsController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		self.render("tools.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/tools", ToolsController, configuration))
		return routes


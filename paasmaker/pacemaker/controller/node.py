from base import BaseController
from base import BaseControllerTest
import unittest
import paasmaker

import tornado
import tornado.testing

class NodeController(BaseController):
	auth_methods = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	def post(self):
		# TODO: Check that we can access
		return self.get()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(register|update)", NodeController, configuration))
		return routes

class NodeControllerTest(BaseControllerTest):
	def get_app(self):
		routes = NodeController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_register(self):
		request = paasmaker.util.apirequest.APIRequest(self.configuration, self.io_loop)
		request.send(self.get_url('/node/register?format=json'), {}, self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('is_heart'))
		self.assertTrue(response.data.has_key('is_pacemaker'))

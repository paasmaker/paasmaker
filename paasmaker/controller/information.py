#!/usr/bin/env python

from base import BaseController
from base import BaseControllerTest
import unittest
import paasmaker

import tornado
import tornado.testing

class InformationController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self):
		self.add_data('is_heart', self.configuration.is_heart())
		self.add_data('is_pacemaker', self.configuration.is_pacemaker())
		self.render("api/apionly.html")

	def post(self):
		return self.get()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/information", InformationController, configuration))
		return routes

class InformationControllerTest(BaseControllerTest):
	def get_app(self):
		routes = InformationController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_information(self):
		request = paasmaker.util.apirequest.APIRequest(self.configuration, self.io_loop)
		request.send(self.get_url('/information?format=json'), {}, self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('is_heart'))
		self.assertTrue(response.data.has_key('is_pacemaker'))

if __name__ == '__main__':
	tornado.testing.main()

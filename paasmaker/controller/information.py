#!/usr/bin/env python

from base import BaseController
from base import BaseControllerTest
import unittest

import tornado
import tornado.testing

class InformationController(BaseController):
	def get(self):
		self.add_data('is_heart', self.configuration.is_heart())
		self.add_data('is_pacemaker', self.configuration.is_pacemaker())
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/information", InformationController, configuration))
		return routes

class InformationControllerTest(BaseControllerTest):
	def get_app(self):
		routes = InformationController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_torando_configuration())
		return application

	def test_information(self):
		self.http_client.fetch(self.get_url('/information?format=json'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertIn("{", response.body)

if __name__ == '__main__':
	tornado.testing.main()

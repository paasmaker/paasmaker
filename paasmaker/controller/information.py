#!/usr/bin/env python

from base import Base
from base import BaseHTTPTest
import unittest

import tornado
import tornado.testing

class Information(Base):
	def get(self):
		self.renderer.add_data('is_heart', self.configuration.is_heart())
		self.renderer.add_data('is_pacemaker', self.configuration.is_pacemaker())
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/information", Information, configuration))
		return routes

class InformationTest(BaseHTTPTest):
	def get_app(self):
		routes = Information.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes)
		return application

	def test_information(self):
		self.http_client.fetch(self.get_url('/information?format=json'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertIn("{", response.body)

if __name__ == '__main__':
	tornado.testing.main()

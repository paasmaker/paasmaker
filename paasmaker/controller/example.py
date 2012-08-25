#!/usr/bin/env python

from base import Base
import unittest

import tornado
import tornado.testing

class Example(Base):
	def get(self):
		self.renderer.add_data("test", "Hello")
		self.renderer.add_data_template("template", "Template")
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example", Example, configuration))
		return routes

class ExampleTest(tornado.testing.AsyncHTTPTestCase):
	def get_app(self):
		# TODO: Use a testing version of the configuration object.
		routes = Example.get_routes({'configuration': 'bar'})
		application = tornado.web.Application(routes)
		return application

	def test_example(self):
		self.http_client.fetch(self.get_url('/example'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertIn("Hello, ", response.body)

if __name__ == '__main__':
	tornado.testing.main()

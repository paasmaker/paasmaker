#!/usr/bin/env python

from base import Base
from base import BaseHTTPTest
import unittest
import json

import tornado
import tornado.testing

class Example(Base):
	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example", Example, configuration))
		return routes

class ExampleFail(Base):
	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		raise Exception('Oh Hai!')
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-fail", ExampleFail, configuration))
		return routes

class ExampleTest(BaseHTTPTest):
	def get_app(self):
		routes = Example.get_routes({'configuration': self.configuration})
		routes.extend(ExampleFail.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_torando_configuration())
		return application

	def test_example(self):
		self.http_client.fetch(self.get_url('/example'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertIn("Hello, ", response.body)

	def test_example_json(self):
		self.http_client.fetch(self.get_url('/example?format=json'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertNotIn("Template", response.body)
		self.assertIn("Hello", response.body)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), 'Missing root data key.')
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertTrue(decoded['data'].has_key('test'), 'Missing test data key.')
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')

	def test_example_fail(self):
		self.http_client.fetch(self.get_url('/example-fail?format=json'), self.stop)
		response = self.wait()
		self.failIf(not response.error)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), 'Missing root data key.')
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(len(decoded['errors']) > 0, 'No errors reported.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertFalse(decoded['data'].has_key('test'), 'Missing test data key.')
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')		

if __name__ == '__main__':
	tornado.testing.main()

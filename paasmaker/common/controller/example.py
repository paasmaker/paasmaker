#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import unittest
import json
import urllib

from base import BaseController
from base import BaseControllerTest

import paasmaker

import colander
import tornado
import tornado.testing

class ExampleDataSchema(colander.MappingSchema):
	more = colander.SchemaNode(colander.String(),
		title="Additional Data")

class ExampleController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		self.add_data_template("json", json)
		self.add_data("raw", self.raw_params)
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example", ExampleController, configuration))
		return routes

class ExampleFailController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		self.add_data_template("json", json)
		self.add_data("raw", self.raw_params)
		raise Exception('Oh Hai!')
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-fail", ExampleFailController, configuration))
		return routes

class ExamplePostController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def post(self):
		if not self.validate_data(ExampleDataSchema()):
			raise tornado.web.HTTPError(400, "Invalid request data.")

		self.add_data("test", "Hello")
		self.add_data("output", int(self.params["more"]))
		self.add_data("raw", self.raw_params)
		self.add_data_template("template", "Template")
		self.add_data_template("json", json)
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-post", ExamplePostController, configuration))
		return routes

##
## TEST CODE
##

class ExampleControllerTest(BaseControllerTest):
	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ExampleController.get_routes({'configuration': self.configuration})
		routes.extend(ExampleFailController.get_routes({'configuration': self.configuration}))
		routes.extend(ExamplePostController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
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

	def test_post_json(self):
		more = 2
		auth = {'method': 'node', 'value': self.configuration.get_flat('node_token')}
		data = {'test': 'bar', 'more': more}
		body = json.dumps({'auth': auth, 'data': data})
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example-post?format=json" % self.get_http_port(),
			method="POST",
			body=body)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.failIf(response.error)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), "Missing data key.")
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(len(decoded['errors']) == 0, 'Errors were reported.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertTrue(decoded['data'].has_key('test'), "Missing test key.")
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')
		self.assertEquals(decoded['data']['output'], more, 'Value was not retained.')

	def test_post_http(self):
		body_parts = []
		body_parts.append(("test", "bar"))
		body_parts.append(("more", "2"))
		body_parts.append(("foo.bar", "test"))
		body_parts.append(("foo2.0", "list"))
		body_parts.append(("foo2.1", "list"))
		body_parts.append(("foo2.[]", "list"))

		body = urllib.urlencode(body_parts)

		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example-post" % self.get_http_port(),
			method="POST",
			body=body)

		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.failIf(response.error)

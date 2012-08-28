#!/usr/bin/env python

import tornado.web
import logging
import paasmaker
import tornado.testing
import warnings
import os

class Base(tornado.web.RequestHandler):

	def initialize(self, configuration):
		self.configuration = configuration

	def prepare(self):
		# TODO: Figure out the path to templates better.
		self.renderer = paasmaker.util.Renderer('templates')

	def render(self, template):
		self.renderer.add_data_template('request', self.request)
		self.renderer.add_data_template('configuration', self.configuration)
		self.renderer.set_format(self.get_argument('format', 'html'))
		if self.renderer.get_format() == 'json':
			self.set_header('Content-Type', 'application/json')
		self.write(self.renderer.render(template))

	def on_finish(self):
		logging.info(
			"%s %s (%s) %0.5fs" %
				(self.request.method,
				self.request.uri,
				self.request.remote_ip,
				self.request.request_time()
				)
		)

class BaseHTTPTest(tornado.testing.AsyncHTTPTestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub()
		super(BaseHTTPTest, self).setUp()
	def tearDown(self):
		self.configuration.cleanup()
		super(BaseHTTPTest, self).tearDown()


#!/usr/bin/env python

import tornado.web
import logging
import paasmaker
import tornado.testing
import warnings
import os
import json

class Base(tornado.web.RequestHandler):

	def initialize(self, configuration):
		self.configuration = configuration
		self.data = {}
		self.template = {}
		self.format = 'html'

	def prepare(self):
		self._set_format(self.get_argument('format', 'html'))

	def add_data(self, key, name):
		self.data[key] = name

	def add_data_template(self, key, name):
		self.template[key] = name

	def _set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format
		
	def render(self, template, **kwargs):
		# Prepare our variables.
		variables = self.data
		if self.format == 'json':
			self.set_header('Content-Type', 'application/json')
			self.write(json.dumps(variables, cls=paasmaker.util.jsonencoder.JsonEncoder))
		elif self.format == 'html':
			# Add in the template variables.
			variables.update(self.template)
			super(Base, self).render(template, **variables)

	def on_finish(self):
		self.application.log_request(self)

class BaseHTTPTest(tornado.testing.AsyncHTTPTestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub()
		super(BaseHTTPTest, self).setUp()
	def tearDown(self):
		self.configuration.cleanup()
		super(BaseHTTPTest, self).tearDown()


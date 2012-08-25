#!/usr/bin/env python

import tornado.web
import logging
import paasmaker

class Base(tornado.web.RequestHandler):

	def initialize(self, configuration):
		self.configuration = configuration

	def prepare(self):
		# TODO: Figure out the path to templates better.
		self.renderer = paasmaker.util.Renderer('templates')

	def render(self, template):
		# TODO: Add template variables from the engine.
		self.renderer.set_format(self.get_argument('format', 'html'))
		if self.renderer.get_format() == 'json':
			print "Setting content-type header."
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

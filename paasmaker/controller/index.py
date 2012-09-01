#!/usr/bin/env python

from base import BaseController

import tornado

class IndexController(BaseController):
	def get(self):
		self.render("index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", IndexController, configuration))
		return routes


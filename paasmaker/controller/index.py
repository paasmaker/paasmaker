#!/usr/bin/env python

from base import Base

import tornado
import tornado.testing

class Index(Base):
	def get(self):
		self.render("index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", Index, configuration))
		return routes


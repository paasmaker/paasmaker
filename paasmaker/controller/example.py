#!/usr/bin/env python

from base import Base

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

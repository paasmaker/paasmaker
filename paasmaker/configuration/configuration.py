#!/usr/bin/env python

import paasmaker

class Configuration:
	def __init__(self, configuration_file_override = None):
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file_override)
		self.values = raw

	def dump(self):
		print str(self.values)

	def get_raw(self):
		return self.values


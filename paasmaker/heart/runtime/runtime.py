#!/usr/bin/env python

# Base runtime interface.
class Runtime():
	def __init__(self, configuration):
		self.configuration = configuration

	def check_system(self):
		raise NotImplementedError("You must implement check_system.")

	def start(self, instance):
		raise NotImplementedError("You must implement start.")

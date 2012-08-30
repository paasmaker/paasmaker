#!/usr/bin/env python

# Base service.
class Base():
	def __init__(self, all_configuration, my_configuration):
		# All configuration is the server-level configuration object.
		self.all_configuration = all_configuration
		# My configuration is just the single section that contains
		# the configuration for this service.
		self.my_configuration = my_configuration
		pass

	def get_server_configuration_schema(self):
		"""
		Get the dotconf schema for validating the incoming server-level
		options. That is, the options used to later provide the service.
		"""
		pass

	def get_application_configuration_schema(self):
		"""
		Get the dotconf schema for validating the
		incoming application-level options. That is, the options
		required to provision the service.
		"""
		pass

	def get_information(self):
		"""
		Get information about this particular service.
		"""
		pass

	def create(self, options):
		"""
		Create the service, using the options supplied by the application.
		Returns a dict containing the credentials used to access the service.
		The returned dict should contain only simple types, as it's
		converted to JSON and supplied to the application.
		"""
		pass

	def remove(self, options, credentials):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.
		"""
		pass


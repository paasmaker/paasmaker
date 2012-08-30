#!/usr/bin/env python

import unittest

# For parsing configuration files.
import dotconf
from dotconf.schema.containers import Section, Value, List
from dotconf.schema.types import Boolean, Integer, Float, String, Regex
from dotconf.parser import DotconfParser, yacc, ParsingError

# Configuration schema.
class RuntimeSection(Section):
	# Required section.
	_meta = { 'repeat': (1, 1), 'args': Value(String()) }
	# Runtime version. Required.
	version = Value(String())

class ServiceSection(Section):
	# Optional section. But you can have as many as you'd like.
	_meta = { 'repeat': (0, None), 'args': Value(String()) }
	# Provider name. Required.
	provider = Value(String())

class PlacementSection(Section):
	# Optional section. And you can only have one.
	_meta = { 'repeat': (0, 1), 'args': Value(String()) }

class MainSection(Section):
	# Hostnames for this application.
	hostnames = List(String())

	# Runtime information.
	runtime = RuntimeSection()

	# Services information.
	service = ServiceSection()

	# Placement information.
	placement = PlacementSection()

class InvalidConfigurationException(Exception):
	pass

class ApplicationConfiguration():
	def __init__(self, application_configuration):
		parser = DotconfParser(application_configuration, debug=False, write_tables=False, errorlog=yacc.NullLogger())
		try:
			config = parser.parse()
		except ParsingError, ex:
			raise InvalidConfigurationException("Invalid configuration file syntax: %s" % str(ex))
		except AttributeError, ex:
			raise InvalidConfigurationException("Parser error - probably invalid configuration file syntax. %s" % str(ex))
		schema = MainSection()
		try:
			self.values = schema.validate(config)
		except dotconf.schema.ValidationError, ex:
			raise InvalidConfigurationException("Configuration is invalid: %s" % str(ex))

	def get_section(self, section):
		"""
		Simple helper to fetch a section. Assumes only one section, and
		that the section exists.
		"""
		return self.values._subsections[section][0]

	def get_sections(self, section):
		"""
		Simple helper to fetch a set of sections.
		"""
		return self.values._subsections[section]

	def get_runtime(self):
		return self.get_section('runtime').args

	def get_runtime_version(self):
		return self.get_section('runtime').get('version')

	def get_hostnames(self):
		return self.values.get('hostnames')

	def get_services(self):
		return self.get_sections('service')

class TestApplicationConfiguration(unittest.TestCase):
	test_config = """
runtime "PHP" {
	version = "5.4"
}
hostnames = "foo.com", "foo.com.au",
		"www.foo.com", "www.foo.com.au"
service "name" {
	provider = "postgres"
	provider_arguments {
		one = "foo"
	}
}

placement "strategy" {
	argument = "test"
}
"""

	bad_config = """
"""
	
	def setUp(self):
		pass

	def tearDown(self):
		pass

	def test_loading(self):
		config = ApplicationConfiguration(self.test_config)
		self.assertEquals(config.get_runtime(), "PHP", "Runtime value is not as expected.")
		self.assertEquals(config.get_runtime_version(), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config.get_hostnames()), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config.get_hostnames(), "Hostnames does not contain an expected item.")
		self.assertEquals(len(config.get_services()), 1, "Services array does not contain the expected number of items.")

	def test_bad_config(self):
		try:
			config = ApplicationConfiguration(self.bad_config)
			self.assertTrue(False, "Should have thrown an exception.")
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Threw exception correctly.")

if __name__ == '__main__':
	unittest.main()

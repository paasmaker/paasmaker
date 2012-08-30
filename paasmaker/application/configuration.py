#!/usr/bin/env python

import unittest
import colander
import yaml

class Runtime(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Runtime name",
		description="Runtime symbolic name")
	version = colander.SchemaNode(colander.String(),
		title="Runtime version",
		description="The version of the runtime to use.")

class Service(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Service name",
		description="Your name for the service to identify it")
	provider = colander.SchemaNode(colander.String(),
		title="Provider name",
		description="Provider symbolic name")
	options = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})

class Services(colander.SequenceSchema):
	service = Service(unknown='preserve')

class Placement(colander.MappingSchema):
	strategy = colander.SchemaNode(colander.String(),
		title="Placement strategy",
		description="The placement strategy to use")

	@staticmethod
	def default():
		return {'strategy': 'default'}

class ConfigurationSchema(colander.MappingSchema):
	hostnames = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String(), title="Hostname"))
	services = Services()
	runtime = Runtime()
	placement = Placement(default=Placement.default(), missing=Placement.default())

class InvalidConfigurationException(Exception):
	pass

class ApplicationConfiguration():
	def __init__(self, raw):
		# Convert to Yaml.
		self.parsed = yaml.load(raw)
		# Load the schema.
		schema = ConfigurationSchema()
		# Parse the structure.
		self.values = schema.deserialize(self.parsed)
		# And flatten.
		self.flat = schema.flatten(self.values)

	def get_flat(self, key):
		return self.flat[key]

	def get_key(self, key):
		return self.values[key]

class TestApplicationConfiguration(unittest.TestCase):
	test_config = """
runtime:
  name: PHP
  version: 5.4

hostnames:
  - foo.com
  - foo.com.au
  - www.foo.com.au
  - www.foo.com

services:
  - name: test
    provider: one
    options:
      bar: foo

placement:
  strategy: default
"""

	bad_config = """
"""
	
	def setUp(self):
		pass

	def tearDown(self):
		pass

	def test_loading(self):
		config = ApplicationConfiguration(self.test_config)
		self.assertEquals(config.get_flat('runtime.name'), "PHP", "Runtime value is not as expected.")
		self.assertEquals(config.get_flat('runtime.version'), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config.get_key('hostnames')), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config.get_key('hostnames'), "Hostnames does not contain an expected item.")
		self.assertEquals(len(config.get_key('services')), 1, "Services array does not contain the expected number of items.")

	def test_bad_config(self):
		try:
			config = ApplicationConfiguration(self.bad_config)
			self.assertTrue(False, "Should have thrown an exception.")
		except colander.Invalid, ex:
			self.assertTrue(True, "Threw exception correctly.")

if __name__ == '__main__':
	unittest.main()

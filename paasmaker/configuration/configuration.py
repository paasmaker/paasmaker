#!/usr/bin/env python

import paasmaker
import collections
import unittest
import os
import logging
import warnings
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# The Configuration Schema.
class ConfigurationSectionEverywhereSchema(colander.MappingSchema):
	http_port = colander.SchemaNode(colander.Int(),
			validator=colander.Range(0, 65535),
			default=8888,
			missing=8888,
			title="API HTTP Port",
			description="The HTTP port to bind to for incoming API requests")
	my_route = colander.SchemaNode(colander.String(),
			default=None,
			missing=None,
			title="My route",
			description="The hostname or IP route to advertise to other nodes",
			required=False)
	auth_token = colander.SchemaNode(colander.String(),
			title="Authentication Token",
			description="Authentication token to use to authenticate with other nodes in the cluster")

class ConfigurationSectionPacemakerSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
			default=False,
			missing=False,
			title="Enable Pacemaker",
			description="If this node should act like a pacemaker")
	dsn = colander.SchemaNode(colander.String(),
			title="Database DSN string",
			default="sqlite:///tmp/paasmaker.db",
			missing="sqlite:///tmp/paasmaker.db",
			description="SQLAlchemy ready database connection string")

class ConfigurationSectionHeartSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
			default=False,
			missing=False,
			title="Enable Heart",
			description="If this node should act like a heart")
	working_dir = colander.SchemaNode(colander.String(),
			title="Working directory",
			default="/tmp/paasmaker-heart/",
			missing="/tmp/paasmaker-heart/",
			description="Working directory where application instances are stored, and other state is stored. Must be writable")


class ConfigurationSchema(colander.MappingSchema):
	everywhere = ConfigurationSectionEverywhereSchema()
	pacemaker = ConfigurationSectionPacemakerSchema()
	heart = ConfigurationSectionHeartSchema()

class InvalidConfigurationException(Exception):
	pass

class Configuration:
	def __init__(self, configuration_file = None):
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file)
		if raw:
			try:
				schema = ConfigurationSchema()
				self.values = schema.deserialize(raw)
				self.flat = schema.flatten(self.values)
			except colander.Invalid, ex:
				# TODO: Pass more context back with this exception - preferably the whole exception.
				raise InvalidConfigurationException("Configuration is not valid: %s" % str(ex))
		else:
			raise InvalidConfigurationException("Unable to parse configuration, or configuration empty - loading '%s'", loader.get_loaded_filename())

	def dump(self):
		logger.debug("Configuration dump:")
		for key in self.flat:
			logger.debug("%s: %s", key, str(self.flat[key]))

	def get_raw(self):
		# TODO: This feels too... raw...
		return self.values
	def get_flat(self, value):
		# TODO: Assumes that the value exists.
		return self.flat[value]

	def is_pacemaker(self):
		return self.flat['pacemaker.enabled']
	def is_heart(self):
		return self.flat['heart.enabled']

class TestConfiguration(unittest.TestCase):
	minimum_config = """
everywhere:
  auth_token: supersecret
pacemaker:
  enabled: true
heart:
  enabled: true
"""
	
	def setUp(self):
		# Ignore the warning when using tmpnam. tmpnam is fine for the test.
		warnings.simplefilter("ignore")

		self.tempnam = os.tempnam()

	def tearDown(self):
		if os.path.exists(self.tempnam):
			os.unlink(self.tempnam)

	def test_fail_load(self):
		try:
			config = Configuration('test_failure.yml')
			self.assertTrue(False, "Should have thrown IOError exception.")
		except IOError, ex:
			self.assertTrue(True, "Threw exception correctly.")

		try:
			open(self.tempnam, 'w').write("test:\n  foo: 10")
			config = Configuration(self.tempnam)
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Configuration did not pass the schema.")

	def test_simple_default(self):
		open(self.tempnam, 'w').write(self.minimum_config)
		config = Configuration(self.tempnam)
		self.assertEqual(config.get_flat('everywhere.http_port'), 8888, 'No default present.')

if __name__ == '__main__':
	unittest.main()

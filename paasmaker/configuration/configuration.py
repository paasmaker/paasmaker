#!/usr/bin/env python

# General imports.
import paasmaker
import unittest
import os
import logging
import tempfile
import uuid
import shutil
import warnings

# For parsing command line options.
from tornado.options import define, options

# For parsing configuration files.
import dotconf
from dotconf.schema.containers import Section, Value, List
from dotconf.schema.types import Boolean, Integer, Float, String, Regex
from dotconf.parser import DotconfParser, yacc, ParsingError

# Set up logging for this module.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Set up command line options.
define("debug", type=int, default=0, help="Enable Tornado debug mode.")

# The Configuration Schema.
class PacemakerSection(Section):
	# Optional section.
	_meta = { 'repeat': (0, 1) }
	# If the pacemaker is enabled.
	enabled = Value(Boolean(), default=False)
	# The SQLAlchemy-ready database DSN. Required.
	dsn = Value(String())

class HeartLanguageVersionSection(Section):
	_meta = { 'repeat': (1, None), 'args': Value(String()) }
	# TODO: Attributes here...
	enabled = Value(Boolean(), default=False)

class HeartLanguageSection(Section):
	_meta = { 'repeat': (1, None), 'args': Value(String()) }
	# A list of versions.
	version = HeartLanguageVersionSection()

class HeartSection(Section):
	# Optional section.
	_meta = { 'repeat': (0, 1) }
	# If the heart is enabled.
	enabled = Value(Boolean(), default=False)
	# The working directory. Required, must be set.
	working_dir = Value(String())
	# Languages that this Heart supports.
	language = HeartLanguageSection()

class MainSection(Section):
	# The HTTP port to listen on.
	http_port = Value(Integer(), default=8888)
	# The route to this node. None if it should be automatically determined.
	my_route = Value(String(), default=None)
	# Authentication token that the nodes use to communicate. Required.
	# Should be 20 characters at least.
	auth_token = Value(Regex(r'[-A-Za-z0-9]{20,}'))
	# Log directory. Very important - you should set this to a persistent location.
	log_directory = Value(String(), default="/tmp/paasmaker-logs/")
	# Server log level.
	server_log_level = Value(Regex(r'DEBUG|INFO|WARNING|CRITICAL|ERROR'), default="INFO")
	# Job log level. TODO: This might need to be upped/downed per job... needs more thinking.
	job_log_level = Value(Regex(r'/DEBUG|INFO|WARNING|CRITICAL|ERROR/'), default="INFO")

	pacemaker = PacemakerSection()
	heart = HeartSection()

class InvalidConfigurationException(Exception):
	pass

class Configuration:
	def __init__(self, configuration_file = None):
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file)
		parser = DotconfParser(raw, debug=False, write_tables=False, errorlog=yacc.NullLogger())
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

	def dump(self):
		logger.debug("Configuration dump:")
		# TODO: Go deeper into the values.
		for key, value in self.values.iteritems():
			logger.debug("%s: %s", key, str(value))

	def get_global(self, key):
		return self.values.get(key)

	def _has_section(self, section):
		return len(self.values._subsections[section]) > 0

	def get_section_value(self, section, key):
		"""Simple helper to fetch a key from a section. Assumes section exists."""
		return self.values._subsections[section][0].get(key)

	def is_pacemaker(self):
		return self._has_section('pacemaker') and self.get_section_value('pacemaker', 'enabled')
	def is_heart(self):
		return self._has_section('heart') and self.get_section_value('heart', 'enabled')

	def get_torando_configuration(self):
		settings = {}
		# TODO: Enforce minimum length on this token.
		# TODO: Use a different value from the auth token?
		settings['cookie_secret'] = self.get_global('auth_token')
		settings['template_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../templates')
		settings['static_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../static')
		settings['debug'] = (options.debug == 1)
		return settings

class ConfigurationStub(Configuration):
	"""A test version of the configuration object, for unit tests."""
	default_config = """
auth_token = '%(auth_token)s'
log_directory = '%(log_dir)s'
"""

	pacemaker_config = """
pacemaker {
	enabled = yes
}
"""

	heart_config = """
heart {
	enabled = yes
	working_dir = "%(heart_working_dir)s"
	language "php" {
		version "5.3" {
			enabled = yes
		}
		version "5.4" {
			enabled = yes
		}
	}
	language "ruby" {
		version "1.8.7" {
			enabled = yes
		}
		version "1.9.3" {
			enabled = yes
		}
	}
}
"""

	def __init__(self, modules=[]):
		# Choose filenames and set up example configuration.
		configfile = tempfile.mkstemp()
		self.params = {}

		self.params['log_dir'] = tempfile.mkdtemp()
		self.params['auth_token'] = str(uuid.uuid4())
		self.params['heart_working_dir'] = tempfile.mkdtemp()

		# Create the configuration file.
		configuration = self.default_config % self.params

		if 'pacemaker' in modules:
			configuration += self.pacemaker_config % self.params
		if 'heart' in modules:
			configuration += self.heart_config % self.params

		self.configname = configfile[1]
		open(self.configname, 'w').write(configuration)

		# Create the object with our temp name.
		Configuration.__init__(self, self.configname)

	def cleanup(self):
		# Remove files that we created.
		shutil.rmtree(self.params['log_dir'])
		shutil.rmtree(self.params['heart_working_dir'])
		os.unlink(self.configname)

class TestConfiguration(unittest.TestCase):
	minimum_config = """
auth_token = '5893b415-f166-41a8-b606-7bdb68b88f0b'
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
			self.assertTrue(True, "Configuration did not pass the schema or was invalid.")

	def test_simple_default(self):
		open(self.tempnam, 'w').write(self.minimum_config)
		config = Configuration(self.tempnam)
		self.assertEqual(config.get_global('http_port'), 8888, 'No default present.')
	
	def test_heart_languages(self):
		stub = ConfigurationStub(['heart'])

if __name__ == '__main__':
	unittest.main()

import unittest
import colander
import yaml
import logging
import os
import tempfile

class NoConfigurationFileException(Exception):
	def __init__(self, paths):
		self.paths = paths

	def __str__(self):
		return "Can't find a configuration file in %s" % str(self.paths)

class InvalidConfigurationException(Exception):
	def __init__(self, colander_exception, raw_configuration, parsed_configuration):
		self.raw_configuration = raw_configuration
		self.parsed_configuration = parsed_configuration
		self.colander_exception = colander_exception

	def __str__(self):
		return "%s" % str(self.colander_exception)

	def report(self):
		# Generate a nice report of what happened here...
		# TODO: Implement this.
		pass
	
class ConfigurationHelper(dict):
	def __init__(self, schema):
		self.parsed = {}
		self.schema = schema
		self.flat = {}

	def load(self, raw):
		# Convert to Yaml.
		self.parsed = yaml.load(raw)
		try:
			# Validate, storing the keys in this dict.
			self.update(self.schema.deserialize(self.parsed))
			# And flatten.
			self.flat = self.schema.flatten(self)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise InvalidConfigurationException(ex, raw, self.parsed)

	def load_from_file(self, search_path):
		for path in search_path:
			if os.path.exists(path):
				# Load this file.
				raw = open(path).read()
				self.load(raw)
				return

		# If we got here... couldn't find a file.
		raise NoConfigurationFileException(search_path)

	def get_flat(self, key):
		return self.flat[key]

	def dump(self):
		for key, value in self.flat.iteritems():
			logging.debug("%s: %s", key, str(value))

class TestConfigurationSchema(colander.MappingSchema):
	str_item = colander.SchemaNode(colander.String())
	map_item = colander.SchemaNode(colander.Mapping())

class TestConfigurationHelper(unittest.TestCase):
	test_configuration = """
str_item: test
map_item:
  one: two
  three: four
"""
	
	def test_simple(self):
		conf = ConfigurationHelper(TestConfigurationSchema())
		conf.load(self.test_configuration)
		self.assertEquals(conf['str_item'], "test", "Can't get string item.")
		self.assertTrue(isinstance(conf['map_item'], dict), "Map item is not a dict.")
		conf.dump()

	def test_from_file(self):
		conf = ConfigurationHelper(TestConfigurationSchema())
		try:
			conf.load_from_file(['a.yaml', 'b.yaml'])
			self.assertTrue(False, "Exception should have been thrown.")
		except NoConfigurationFileException, ex:
			self.assertTrue(True, "Exception was thrown.")

		configfile = tempfile.mkstemp()
		configname = configfile[1]
		open(configname, 'w').write(self.test_configuration)

		conf.load_from_file(['a.yaml', configname])
		self.assertTrue(True, "Successfully loaded file.")
		os.unlink(configname)

	def test_empty(self):
		conf = ConfigurationHelper(TestConfigurationSchema())
		try:
			conf.load("")
			self.assertTrue(False, "Exception should have been thrown.")
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Exception was thrown.")


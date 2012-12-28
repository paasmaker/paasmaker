import unittest
import colander
import yaml
import logging
import os
import tempfile

class NoConfigurationFileException(Exception):
	"""
	Exception thrown when unable to find a configuration file in
	the supplied search paths.
	"""
	def __init__(self, paths):
		self.paths = paths

	def __str__(self):
		return "Can't find a configuration file in %s" % str(self.paths)

class InvalidConfigurationException(Exception):
	"""
	Exception thrown when the configuration is invalid for
	some reason.

	:arg colander.Invalid colander_exception: The colander.Invalid
		source exception, if this error originated from Colander.
	:arg str raw_configuration: The raw configuration text.
	:arg dict parsed_configuration: The parsed configuration, if available.
	"""
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
	"""
	A configuration helper base class. Provides helpers for other
	configuration objects, to help with parsing and error handling.

	:arg colander.Schema schema: The Schema used to validate the
		incoming configuration.
	"""
	def __init__(self, schema):
		self.filename = None
		self.parsed = {}
		self.schema = schema
		self.flat = {}
		self.raw = None

	def load(self, raw):
		"""
		Load the given raw configuration, and validate it against
		the Colander schema. Raises an InvalidConfigurationException
		on error.

		:arg str raw: The raw configuration, in Yaml format.
		"""
		# Convert to Yaml.
		# NOTE: We always use safe_load, the yaml should have no reason
		# to make Python classes.
		self.parsed = yaml.safe_load(raw)
		try:
			# Validate, storing the keys in this dict.
			self.update(self.schema.deserialize(self.parsed))
			# And flatten.
			self.flat = self.schema.flatten(self)
			self.raw = raw
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise InvalidConfigurationException(ex, raw, self.parsed)

		# Allow subclasses to run their post-load stuff.
		self.post_load()

	def update_flat(self):
		"""
		Update the internal flat representation of the configuration,
		from the current dict of settings.

		Intended to be used when the dict of settings changes.
		"""
		self.flat = self.schema.flatten(self)

	def post_load(self):
		"""
		Overide this in your subclass to check the data that you loaded.
		This is called immediately after the data is parsed and flattened.
		"""
		pass

	def load_from_file(self, search_path):
		"""
		Load the configuration from one of the paths supplied.
		Raises a NoConfigurationFileException if it can not
		find a file in the search path.

		:arg list search_path: The paths to check for existence.
			The first existing path is loaded.
		"""
		for path in search_path:
			if os.path.exists(path):
				# Load this file.
				raw = open(path).read()
				self.filename = path
				self.load(raw)
				return

		# If we got here... couldn't find a file.
		raise NoConfigurationFileException(search_path)

	def get_flat(self, key):
		"""
		Get a configuration entry by its flat key.

		For example, 'pacemaker.enabled' returns
		the value from self['pacemaker']['enabled'].

		For full details on how this works, read up on
		how Colander flattens data structures.
		"""
		return self.flat[key]

	def dump(self):
		"""
		Dump the contents of this configuration object to the
		debug log stream.
		"""
		keys = self.flat.keys()
		keys.sort()
		for key in keys:
			logging.debug("%s: %s", key, str(self.flat[key]))

	def load_plugins(self, registry, datasource):
		"""
		Load the plugins from the given data source,
		into the given registry. This is used by the main
		configuration to quickly load plugins.

		:arg PluginRegistry registry: The plugin registry to load
			plugins into.
		:arg list datasource: The data source describing the
			plugins.
		"""
		for entry in datasource:
			name = entry['name']
			klass = entry['class']
			params = entry['parameters']
			title = entry['title']

			registry.register(name, klass, params, title)

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


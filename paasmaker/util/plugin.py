
import unittest
import paasmaker
import colander
import logging
from paasmaker.common.core.constants import Enum

# From http://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname
def get_class( kls ):
	parts = kls.split('.')
	module = ".".join(parts[:-1])
	m = __import__( module )
	for comp in parts[1:]:
		m = getattr(m, comp)
	return m

# For each plugin mode, the flag indicates if it accepts parameters or not.
MODE_REQUIRE_PARAMS = {
	'TEST_PARAM': True,
	'TEST_NOPARAM': False,
	'SERVICE_CREATE': True,
	'SERVICE_STARTUP': False,
	'RUNTIME_STARTUP': True,
	'RUNTIME_VERSIONS': False,
	'SCM_EXPORT': True,
	'SCM_LIST': False,
	'PREPARE_COMMAND': True,
	'PLACEMENT': True
}

# Mode constants.
MODE = Enum(MODE_REQUIRE_PARAMS.keys())

class Plugin(object):
	"""
	A subclass for your classes to make them into plugins.
	Note that you need the __init__ method supplied by this
	class.
	To use, you will need to give your plugin modes (by setting
	your subclasses' class variable 'MODES' and also OPTIONS_SCHEMA
	with a colander schema for your options, and if one of your modes
	requires it, PARAMETERS_SCHEMA.
	"""
	MODES = []
	OPTIONS_SCHEMA = None
	PARAMETERS_SCHEMA = None

	def __init__(self, configuration, mode, options, parameters, logger=None):
		self.configuration = configuration
		self.raw_options = options
		self.raw_parameters = parameters
		self.mode = mode

		if not logger:
			# Create a logger for the plugins use.
			self.logger = logging.getLogger('paasmaker.plugin.' + self.__class__.__name__)
			self.logger.addHandler(logging.NullHandler())
		else:
			# Use the supplied logger. Subclasses should use this.
			self.logger = logger

	def check_options(self):
		"""
		Helper function to validate the options supplied when instantiated,
		and to throw an exception if it fails. This stores a flat version
		of the options for your subclasses's convenience.
		"""
		try:
			# Validate.
			self.options = self.OPTIONS_SCHEMA.deserialize(self.raw_options)
			# And flatten.
			self.options_flat = self.OPTIONS_SCHEMA.flatten(self.options)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise paasmaker.common.configuration.InvalidConfigurationException(ex, '', self.raw_options)

	def check_parameters(self):
		"""
		Helper function to validate the parameters supplied when instantiated,
		and to throw an exception if it fails. This also stores a flat version
		of the parameters for your subclasses's convenience.
		"""
		try:
			# Validate.
			self.parameters = self.PARAMETERS_SCHEMA.deserialize(self.raw_parameters)
			# And flatten.
			self.parameters_flat = self.PARAMETERS_SCHEMA.flatten(self.parameters)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise paasmaker.common.configuration.InvalidConfigurationException(ex, '', self.raw_parameters)

	def get_flat_option(self, key):
		return self.options_flat[key]
	def get_flat_parameter(self, key):
		return self.parameters_flat[key]

class PluginRegistry:
	"""
	A plugin registry.
	This matches tag names (eg, "paasmaker.service.foo") to classes (which should
	be an importable fully dotted class - doesn't have to be in the paasmaker module).
	When prompted, it can instantiate them. Plugins should be a subclass of Plugin
	which allows them to receive parameters appropriately on startup.

	Why not just allow the fully dotted class in configurations? Because then
	people could instantiate Python objects directly. This requires the classes
	to be set explicitly. It also seperates the names in configurations from
	users, so sysadmins could switch out implementations if they needed to, or
	have alternate versions for their needs with different configuration.

	Finally, the reason to use plugins is that it splits global configuration for
	the plugins and the runtime parameters, which come from different sources.
	"""

	def __init__(self, configuration):
		self.configuration = configuration
		# Map plugin name to class.
		self.class_registry = {}
		# Map plugin name to it's options.
		self.options_registry = {}
		# Map mode to a list of plugins.
		self.mode_registry = {}

	def register(self, plugin, klass, options):
		# Find the class object that matches the supplied string name.
		former = get_class(klass)

		# Make sure it's a subclass of the plugin.
		if not issubclass(former, Plugin):
			raise ValueError("Supplied class is not a Plugin.")

		# See if we have an options schema.
		if not former.OPTIONS_SCHEMA:
			raise ValueError("Supplied class has no options schema.")

		# Validate the options supplied.
		try:
			options_schema = former.OPTIONS_SCHEMA
			options_schema.deserialize(options)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise paasmaker.common.configuration.InvalidConfigurationException(ex, '', options)

		# Make sure it has some modes of operation.
		if len(former.MODES) == 0:
			raise ValueError("Supplied class has no modes.")

		# If we got here, all good!
		self.class_registry[plugin] = klass
		self.options_registry[plugin] = options

		# Now go ahead and put it into the mode registry.
		for mode in former.MODES:
			if not self.mode_registry.has_key(mode):
				self.mode_registry[mode] = []
			self.mode_registry[mode].append(plugin)
			if MODE_REQUIRE_PARAMS[mode] and not former.PARAMETERS_SCHEMA:
				raise ValueError("Supplied class does not have a parameter schema, but has a mode that accepts parameters.")

	def exists(self, plugin, mode):
		has_class = self.class_registry.has_key(plugin)
		has_mode = self.mode_registry.has_key(mode) and (plugin in self.mode_registry[mode])
		return has_class and has_mode

	def class_for(self, plugin):
		klass = get_class(self.class_registry[plugin])
		return klass

	def instantiate(self, plugin, mode, parameters=None, logger=None):
		klass = get_class(self.class_registry[plugin])
		if mode not in klass.MODES:
			raise ValueError("Plugin %s does not have mode %s" % (plugin, mode))

		instance = klass(self.configuration, mode, self.options_registry[plugin], parameters, logger)

		# Get it to recheck options.
		instance.check_options()

		# And recheck parameters if it requires them.
		if MODE_REQUIRE_PARAMS[mode] and not parameters:
			raise ValueError("Plugin %s requires parameters but none were passed.")
		if MODE_REQUIRE_PARAMS[mode]:
			instance.check_parameters()

		return instance

	def plugins_for(self, mode):
		if not self.mode_registry.has_key(mode):
			# No plugins match this mode.
			return []
		else:
			# Return the list of them.
			return self.mode_registry[mode]

class PluginExampleOptionsSchema(colander.MappingSchema):
	# Required key.
	option1 = colander.SchemaNode(colander.String())
	option2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExampleParametersSchema(colander.MappingSchema):
	# Required key.
	parameter1 = colander.SchemaNode(colander.String())
	parameter2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExample(Plugin):
	MODES = [MODE.TEST_PARAM, MODE.TEST_NOPARAM]
	OPTIONS_SCHEMA = PluginExampleOptionsSchema()
	PARAMETERS_SCHEMA = PluginExampleParametersSchema()

	def do_nothing(self):
		pass

class TestExample(unittest.TestCase):
	def test_plugin_registration(self):
		#print str(registry)
		registry = PluginRegistry(2)

		self.assertFalse(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin already exists?")

		registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {'option1': 'test'})

		self.assertTrue(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin doesn't exist.")

		instance = registry.instantiate('paasmaker.test', MODE.TEST_PARAM, {'parameter1': 'test'})
		instance.do_nothing()

		self.assertTrue(isinstance(instance, PluginExample), "Instance is not a PluginExample")
		self.assertEquals(instance.configuration, 2, "Configuration was not passed to instance.")
		self.assertEquals(instance.get_flat_option('option1'), 'test', 'Flat option not present.')
		self.assertEquals(instance.get_flat_parameter('parameter1'), 'test', 'Flat parameter not present.')

	def test_plugin_bad_options(self):
		registry = PluginRegistry(2)
		try:
			registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {})
			self.assertTrue(False, "Should have thrown exception.")
		except paasmaker.common.configuration.configuration.InvalidConfigurationException, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

	def test_plugin_bad_parameters(self):
		registry = PluginRegistry(2)
		registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {'option1': 'test'})
		try:
			instance = registry.instantiate('paasmaker.test', MODE.TEST_PARAM, {'foo': 'bar'})
			self.assertTrue(False, "Should have thrown exception.")
		except paasmaker.common.configuration.configuration.InvalidConfigurationException, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

	def test_plugin_no_parameters(self):
		registry = PluginRegistry(2)
		registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {'option1': 'test'})
		try:
			instance = registry.instantiate('paasmaker.test', MODE.TEST_PARAM)
			self.assertTrue(False, "Should have thrown exception.")
		except ValueError, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")


import unittest
import logging

import paasmaker

from paasmaker.common.core.constants import Enum
from paasmaker.util.configurationhelper import InvalidConfigurationParameterException
from paasmaker.util.configurationhelper import InvalidConfigurationFormatException

import colander

# From http://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname
def get_class(kls):
	"""
	Helper function to get a class from its
	fully qualified name.

	:arg str kls: The class name to fetch.
	"""
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

	# Called before the HTTP server is listening.
	'STARTUP_ASYNC_PRELISTEN': False,
	# Called after the HTTP server is listening. Can't abort server startup.
	'STARTUP_ASYNC_POSTLISTEN': False,
	'STARTUP_ROUTES': False,

	# Called before we've notified the master server that we're down.
	'SHUTDOWN_PRENOTIFY': False,
	# Called after we've notified the master server that we're down.
	'SHUTDOWN_POSTNOTIFY': False,

	'SERVICE_CREATE': True,
	'SERVICE_DELETE': False,

	# This is for plugins that can run as startup commands for applications.
	'RUNTIME_STARTUP': True,
	 # This is for plugins that can actually execute applications.
	'RUNTIME_EXECUTE': True,
	'RUNTIME_VERSIONS': False,
	'RUNTIME_ENVIRONMENT': True,

	'SCM_EXPORT': True,
	'SCM_FORM': False,
	'SCM_LIST': False,

	'PREPARE_COMMAND': True,

	'PLACEMENT': True,

	'USER_AUTHENTICATE_PLAIN': False,
	'USER_AUTHENTICATE_EXTERNAL': False,

	'JOB': True,

	'HEALTH_CHECK': True,
	'PERIODIC': False,

	'NODE_DYNAMIC_TAGS': False,
	'NODE_STATS': False,
	'NODE_SCORE': False,

	'PACKER': False,
	'UNPACKER': False,
	'FETCHER': False,
	'STORER': False
}

# Mode constants.
MODE = Enum(MODE_REQUIRE_PARAMS.keys())

API_VERSION = "0.9.0"

class Plugin(object):
	"""
	A subclass for your classes to make them into plugins.
	Note that you need the __init__ method supplied by this
	class, and should not override it.

	To use, you will need to give your plugin metadata, that
	indicate what modes it runs in, and also any options schema.
	"""
	MODES = {}
	OPTIONS_SCHEMA = None

	def __init__(self, configuration, mode, options, parameters, called_name, logger=None):
		self.configuration = configuration
		self.raw_options = options
		self.raw_parameters = parameters
		self.mode = mode
		self.called_name = called_name

		if not logger:
			# Create a logger for the plugins use.
			self.logger = logging.getLogger('paasmaker.plugin.' + self.__class__.__name__)
			self.logger.addHandler(logging.NullHandler())
		else:
			# Use the supplied logger. Subclasses should use this.
			self.logger = logger

	def _check_options(self):
		"""
		Helper function to validate the options supplied when instantiated,
		and to throw an exception if it fails. This stores a flat version
		of the options for your subclasses's convenience.

		Typically this is only called by the plugin registry itself.
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
			raise InvalidConfigurationFormatException(ex, '', self.raw_options)

	def _check_parameters(self, mode):
		"""
		Helper function to validate the parameters supplied when instantiated,
		and to throw an exception if it fails. This also stores a flat version
		of the parameters for your subclasses's convenience.

		Typically this is only called by the plugin registry itself.
		"""
		try:
			# Validate.
			self.parameters = self.MODES[mode].deserialize(self.raw_parameters)
			# And flatten.
			self.parameters_flat = self.MODES[mode].flatten(self.parameters)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise InvalidConfigurationFormatException(ex, '', self.raw_parameters)

	def get_flat_option(self, key):
		"""
		Get a flat option from the plugin's configured options.

		:arg str key: The key to fetch.
		"""
		return self.options_flat[key]

	def get_flat_parameter(self, key):
		"""
		Get a flat parameter from the plugin's parameters.

		:arg str key: The key to fetch.
		"""
		return self.parameters_flat[key]

class PluginRegistry(object):
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
	register multiple versions for their needs with different configuration.

	Finally, the reason to use plugins is that it splits global configuration for
	the plugins and the runtime parameters, which come from different sources. Not
	all plugins have runtime options, however.
	"""

	def __init__(self, configuration):
		self.configuration = configuration
		# Map plugin name to class.
		self.class_registry = {}
		# Map plugin name to it's options.
		self.options_registry = {}
		# Map mode to a list of plugins.
		self.mode_registry = {}
		# A flat set of modes supported by a plugin.
		self.class_modes = {}
		# Map plugin name to it's title.
		self.title_registry = {}

	def register(self, plugin, klass, options, title):
		"""
		Register a plugin with this registry.

		:arg str plugin: The symbolic name of the plugin.
		:arg str klass: The fully dotted importable path to
			the class that provides this plugin.
		:arg dict options: The options for this plugin.
		:arg str title: A title used when displaying this
			plugin to the user.
		"""
		# Find the class object that matches the supplied string name.
		try:
			former = get_class(klass)
		except AttributeError, ex:
			# Module doesn't contain that class file.
			raise ValueError("The module for %s does not contain the named class." % klass)
		except ImportError, ex:
			# No such module.
			raise ValueError("The module for %s does not exist." % klass)

		# Make sure it's a subclass of the plugin.
		if not issubclass(former, Plugin):
			raise ValueError("Supplied class is not a Plugin.")

		# See if we have an options schema.
		if not former.OPTIONS_SCHEMA:
			raise ValueError("Supplied class has no options schema.")

		# Check the API version.
		if not hasattr(former, 'API_VERSION'):
			raise ValueError("Supplied plugin does not specify an API version.")
		if former.API_VERSION < API_VERSION:
			raise ValueError("Plugin's API version %s does not match our API version %s." % (former.API_VERSION, API_VERSION))

		# Validate the options supplied.
		try:
			options_schema = former.OPTIONS_SCHEMA
			options_schema.deserialize(options)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise InvalidConfigurationFormatException(ex, '', options)

		# Make sure it has some modes of operation.
		if len(former.MODES) == 0:
			raise ValueError("Supplied class has no modes.")

		# If we already have the plugin, remove it first,
		# and then add it again. This is in case the replacement
		# has different modes - we don't want to double register it.
		if plugin in self.class_registry:
			self.deregister(plugin)

		# If we got here, all good!
		self.class_registry[plugin] = klass
		self.options_registry[plugin] = options
		self.title_registry[plugin] = title

		# Now go ahead and put it into the mode registry.
		for mode in former.MODES.keys():
			if not self.mode_registry.has_key(mode):
				self.mode_registry[mode] = []
			self.mode_registry[mode].append(plugin)
			if MODE_REQUIRE_PARAMS[mode] and not former.MODES[mode]:
				raise ValueError("Supplied class does not have a parameter schema, but has a mode that accepts parameters.")
		self.class_modes[plugin] = former.MODES.keys()

	def deregister(self, plugin):
		"""
		De-register a plugin with this registry. This cleans up all the internal
		data structures.

		:arg str plugin: The symbolic name of the plugin.
		"""
		del self.class_registry[plugin]
		del self.options_registry[plugin]
		del self.title_registry[plugin]

		for mode in self.class_modes[plugin]:
			self.mode_registry[mode].remove(plugin)

	def exists(self, plugin, mode):
		"""
		Check to see if a plugin exists, for the given mode.

		:arg str plugin: The plugin to test.
		:arg str mode: The mode to test for.
		"""
		has_class = self.class_registry.has_key(plugin)
		has_mode = self.mode_registry.has_key(mode) and (plugin in self.mode_registry[mode])
		return has_class and has_mode

	def title(self, plugin):
		"""
		Return the title of the given plugin.

		:arg str plugin: The plugin to fetch the title for.
		"""
		if not self.title_registry.has_key(plugin):
			raise ValueError("No such plugin %s" % plugin)
		return self.title_registry[plugin]

	def instantiate(self, plugin, mode, parameters=None, logger=None):
		"""
		Instantiate a plugin and return the instance of the plugin.

		If the plugin takes runtime parameters, pass those in to this
		function. If you do not pass parameters and the plugin
		requires them, a ValueError exception will be raised.

		Where possible, pass in an appropriate job logger for the
		logger parameter. This will allow the plugin to log to the
		appropriate place. If you don't pass one in, the plugin
		will choose one to write to on startup - but will probably
		not be what you want.

		:arg str plugin: The plugin to instantiate.
		:arg str mode: The mode to put the plugin into.
		:arg dict|None parameters: The runtime parameters
			for the plugin, or None if it requires none.
		:arg LoggerAdapter logger: The logging adapter, passed into
			the plugin to allow it to log to the correct location.
		"""
		klass = get_class(self.class_registry[plugin])
		if not klass.MODES.has_key(mode):
			raise ValueError("Plugin %s does not have mode %s" % (plugin, mode))

		instance = klass(self.configuration, mode, self.options_registry[plugin], parameters, plugin, logger)

		# Get it to recheck options.
		instance._check_options()

		# And recheck parameters if it requires them.
		if MODE_REQUIRE_PARAMS[mode]:
			if parameters is None:
				raise ValueError("Plugin %s requires parameters but none were passed." % plugin)
			elif not instance.MODES.has_key(mode):
				raise ValueError("Plugin %s does not have a paramters schema, but it should." % plugin)
			else:
				instance._check_parameters(mode)

		return instance

	def plugins_for(self, mode):
		"""
		Fetch a list of plugins that can be instantiated in the given
		mode. Used to build lists of available services, SCMs, or other
		internal providers.

		A list of only the symbolic plugin names is returned.

		:arg str mode: The mode to search for.
		"""
		if not self.mode_registry.has_key(mode):
			# No plugins match this mode.
			return []
		else:
			# Return the list of them. A copy.
			return list(self.mode_registry[mode])

	def plugin_information(self):
		"""
		Return a dict of information about registered plugins.

		This includes the configuration of plugins, and as such
		may contain sensitive information.
		"""
		result = {}

		for name in self.class_registry:
			this_plugin = {}
			this_plugin['name'] = name
			this_plugin['options'] = self.options_registry[name]
			this_plugin['modes'] = self.class_modes[name]
			this_plugin['title'] = self.title_registry[name]

			result[name] = this_plugin

		return result

class PluginExampleOptionsSchema(colander.MappingSchema):
	# Required key.
	option1 = colander.SchemaNode(colander.String())
	option2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExampleParametersSchema(colander.MappingSchema):
	# Required key.
	parameter1 = colander.SchemaNode(colander.String())
	parameter2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExample(Plugin):
	"""
	An example plugin, showing how to use the plugin API.

	View the source code to get a full description of the code.

	See above this class for example Colander schemas for options
	and parameters.
	"""
	MODES = {
		MODE.TEST_PARAM: PluginExampleParametersSchema(),
		MODE.TEST_NOPARAM: None
	}
	OPTIONS_SCHEMA = PluginExampleOptionsSchema()
	API_VERSION = "0.9.0"

	def do_nothing(self):
		# Various base plugins will define the signatures of functions
		# that you need to implement.

		# You can get your called name - your symbolic name - with
		# this parameter:
		called_name = self.called_name
		# This can be useful to create temporary or persistent files
		# that won't conflict with other plugins.

		# When logging - get the stored logger:
		self.logger.info("This is an example message.")

		# Every plugin is passed a Configuration object. This is the
		# global configuration object. On it is also the Tornado
		# IOLoop - you should always use this one rather than the global
		# one, which makes your code unit testable easily.
		global_config = self.configuration
		# io_loop = self.configuration.io_loop

		# To fetch out your configuration options:
		opt = self.options['option1']
		opt = self.get_flat_option('option1')

		# Or if you have something special that Colander can't handle:
		opt = self.raw_options['option1']

		# For runtime parameters (if required/supplied):
		runtime_opt = self.parameters['parameter1']
		runtime_opt = self.get_flat_parameter('parameter1')

		# Or if you have something special that Colander can't handle:
		runtime_opt = self.raw_parameters['parameter1']

class TestExample(unittest.TestCase):
	def test_plugin_registration(self):
		#print str(registry)
		registry = PluginRegistry(2)

		self.assertFalse(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin already exists?")

		registry.register(
			'paasmaker.test',
			'paasmaker.util.PluginExample',
			{'option1': 'test'},
			"Test Plugin"
		)

		self.assertTrue(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin doesn't exist.")

		instance = registry.instantiate(
			'paasmaker.test',
			MODE.TEST_PARAM,
			{'parameter1': 'test'}
		)
		instance.do_nothing()

		self.assertTrue(isinstance(instance, PluginExample), "Instance is not a PluginExample")
		self.assertEquals(instance.configuration, 2, "Configuration was not passed to instance.")
		self.assertEquals(instance.get_flat_option('option1'), 'test', 'Flat option not present.')
		self.assertEquals(instance.get_flat_parameter('parameter1'), 'test', 'Flat parameter not present.')

	def test_plugin_registration_bad_class(self):
		#print str(registry)
		registry = PluginRegistry(2)

		# Valid module, bad class.
		try:
			registry.register(
				'paasmaker.test',
				'paasmaker.util.PluginExampleNot',
				{'option1': 'test'},
				"Test Plugin"
			)

			self.assertTrue(False, "Should have raised exception.")
		except ValueError, ex:
			self.assertIn("does not contain the named class", str(ex))
			self.assertTrue(True, "Raised exception correctly.")

		# Invalid module.
		try:
			registry.register(
				'paasmaker.test',
				'paasmaker.invalid.PluginExampleNot',
				{'option1': 'test'},
				"Test Plugin"
			)

			self.assertTrue(False, "Should have raised exception.")
		except ValueError, ex:
			self.assertIn("does not exist", str(ex))
			self.assertTrue(True, "Raised exception correctly.")

	def test_plugin_deregistration(self):
		#print str(registry)
		registry = PluginRegistry(2)

		self.assertFalse(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin already exists?")

		registry.register(
			'paasmaker.test',
			'paasmaker.util.PluginExample',
			{'option1': 'test'},
			"Test Plugin"
		)

		self.assertTrue(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin doesn't exist.")

		registry.deregister('paasmaker.test')

		self.assertFalse(registry.exists('paasmaker.test', MODE.TEST_PARAM), "Plugin still exists!")

	def test_plugin_bad_options(self):
		registry = PluginRegistry(2)
		try:
			registry.register(
				'paasmaker.test',
				'paasmaker.util.PluginExample',
				{},
				"Test Plugin"
			)
			self.assertTrue(False, "Should have thrown exception.")
		except paasmaker.common.configuration.configuration.InvalidConfigurationFormatException, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

	def test_plugin_bad_parameters(self):
		registry = PluginRegistry(2)
		registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {'option1': 'test'}, "Test Plugin")
		try:
			instance = registry.instantiate(
				'paasmaker.test',
				MODE.TEST_PARAM,
				{'foo': 'bar'}
			)
			self.assertTrue(False, "Should have thrown exception.")
		except paasmaker.common.configuration.configuration.InvalidConfigurationFormatException, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

	def test_plugin_no_parameters(self):
		registry = PluginRegistry(2)
		registry.register(
			'paasmaker.test',
			'paasmaker.util.PluginExample',
			{'option1': 'test'},
			"Test Plugin"
		)
		try:
			instance = registry.instantiate('paasmaker.test', MODE.TEST_PARAM)
			self.assertTrue(False, "Should have thrown exception.")
		except ValueError, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

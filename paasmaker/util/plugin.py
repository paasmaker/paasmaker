
import unittest
import paasmaker
import colander

# From http://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname
def get_class( kls ):
	parts = kls.split('.')
	module = ".".join(parts[:-1])
	m = __import__( module )
	for comp in parts[1:]:
		m = getattr(m, comp)
	return m

class PluginMixin(object):
	def get_options_schema(self):
		raise NotImplementedError("You must implement get_options_schema")
	def get_parameters_schema(self):
		raise NotImplementedError("You must implement get_parameters_schema")

	def __init__(self, configuration, options, parameters):
		self.configuration = configuration
		self.raw_options = options
		self.raw_parameters = parameters

	def check_options(self):
		try:
			# Validate.
			options_schema = self.get_options_schema()
			self.options = options_schema.deserialize(self.raw_options)
			# And flatten.
			self.options_flat = options_schema.flatten(self.options)
		except colander.Invalid, ex:
			# Raise another exception that encapsulates more context.
			# In future this can be used to print a nicer report.
			# Because the default output is rather confusing...!
			raise paasmaker.common.configuration.InvalidConfigurationException(ex, '', self.raw_options)

	def check_parameters(self):
		try:
			# Validate.
			parameters_schema = self.get_parameters_schema()
			self.parameters = parameters_schema.deserialize(self.raw_parameters)
			# And flatten.
			self.parameters_flat = parameters_schema.flatten(self.parameters)
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
	be an importable fully dotted class).
	When prompted, it can instantiate them. It assumes any plugins require three
	arguments to the constructor:
	* Global configuration object.
	* Plugin options (a dict) (validated at registration time)
	* Parameters (a dict) (validated at instantiation time)
	Why not just allow the fully dotted class in configurations? Because then
	people could instantiate Python objects directly. This requires the classes
	to be set explicitly. It also seperates the names in configurations from
	users, so sysadmins could switch out implementations if they needed to, or
	have alternate versions for their needs with different configuration.
	To make it easier, use the PluginMixin.
	"""

	def __init__(self, configuration):
		self.configuration = configuration
		self.class_registry = {}
		self.data_registry = {}

	def register(self, plugin, cls, data):
		# Validate data.
		# This will throw an exception if it fails.
		former = get_class(cls)
		instance = former(self.configuration, data, {})
		instance.check_options()

		# If we got here, all good!
		self.class_registry[plugin] = cls
		self.data_registry[plugin] = data

	def exists(self, plugin):
		return self.class_registry.has_key(plugin)

	def class_for(self, plugin):
		cls = get_class(self.class_registry[plugin])
		return cls

	def instantiate(self, plugin, parameters):
		cls = get_class(self.class_registry[plugin])
		instance = cls(self.configuration, self.data_registry[plugin], parameters)

		# Get it to recheck options, and also parameters - this unpacks it as well.
		instance.check_options()
		instance.check_parameters()

		return instance

class PluginExampleOptionsSchema(colander.MappingSchema):
	# Required key.
	option1 = colander.SchemaNode(colander.String())
	option2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExampleParametersSchema(colander.MappingSchema):
	# Required key.
	parameter1 = colander.SchemaNode(colander.String())
	parameter2 = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class PluginExample(PluginMixin):
	def get_options_schema(self):
		return PluginExampleOptionsSchema()
	def get_parameters_schema(self):
		return PluginExampleParametersSchema()

class TestExample(unittest.TestCase):
	def test_plugin_registration(self):
		#print str(registry)
		registry = PluginRegistry(2)

		self.assertFalse(registry.exists('paasmaker.test'), "Plugin already exists?")

		registry.register('paasmaker.test', 'paasmaker.util.PluginExample', {'option1': 'test'})

		self.assertTrue(registry.exists('paasmaker.test'), "Plugin doesn't exist.")

		instance = registry.instantiate('paasmaker.test', {'parameter1': 'test'})

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
			instance = registry.instantiate('paasmaker.test', {})
			self.assertTrue(False, "Should have thrown exception.")
		except paasmaker.common.configuration.configuration.InvalidConfigurationException, ex:
			self.assertTrue(True, "Didn't throw exception as expected.")

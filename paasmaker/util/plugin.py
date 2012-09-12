
import unittest

# From http://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname
def get_class( kls ):
	parts = kls.split('.')
	module = ".".join(parts[:-1])
	m = __import__( module )
	for comp in parts[1:]:
		m = getattr(m, comp)
	return m

class PluginRegistry:
	"""
	A plugin registry.
	This matches tag names (eg, "paasmaker.service.foo") to classes (which should
	be an importable fully dotted class).
	When prompted, it can instantiate them. It assumes any plugins
	require two arguments to the constructor: configuration and parameters.
	Why not just allow the fully dotted class in configurations? Because then
	people could instantiate Python objects directly. This requires the classes
	to be set explicitly. It also seperates the names in configurations from
	users, so sysadmins could switch out implementations if they needed to.
	"""
	registry = {}

	def __init__(self, configuration):
		self.configuration = configuration

	def register(self, plugin, cls):
		self.registry[plugin] = cls

	def exists(self, plugin):
		return self.registry.has_key(plugin)

	def instantiate(self, plugin, parameters):
		cls = get_class(self.registry[plugin])
		return cls(self.configuration, parameters)

class PluginExample:
	def __init__(self, configuration, parameters):
		self.configuration = configuration
		self.parameters = parameters

	def hello(self):
		return self.configuration

class TestExample(unittest.TestCase):
	def setUp(self):
		self.registry = PluginRegistry(2)

	def test_plugin(self):
		self.assertFalse(self.registry.exists('paasmaker.test'), "Plugin already exists?")

		self.registry.register('paasmaker.test', 'paasmaker.util.PluginExample')

		self.assertTrue(self.registry.exists('paasmaker.test'), "Plugin doesn't exist.")

		instance = self.registry.instantiate('paasmaker.test', {})

		self.assertTrue(isinstance(instance, PluginExample), "Instance is not a PluginExample")
		self.assertEquals(instance.configuration, 2, "Configuration was not passed to instance.")

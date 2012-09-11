import unittest
import colander
import yaml
import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationException

# Schema definition.
class Runtime(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Runtime name",
		description="Runtime symbolic name")
	version = colander.SchemaNode(colander.String(),
		title="Runtime version",
		description="The version of the runtime to use.")
	startup = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()),
		title="Startup commands",
		description="Commands used to prepare the code before starting the instance.",
		default=[],
		missing=[])

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

class ApplicationSource(colander.MappingSchema):
	method = colander.SchemaNode(colander.String(),
		title="Source fetching method",
		description="The method to grab and prepare the source")
	location = colander.SchemaNode(colander.String(),
		title="Location of source",
		description="The location to fetch the source from.")
	prepare = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()),
		title="Prepare commands",
		description="Commands used to prepare a pristine source for execution.")

class Application(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Application name",
		decription="The name of the application")
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})
	source = ApplicationSource()

class ConfigurationSchema(colander.MappingSchema):
	application = Application()
	hostnames = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()), title="Hostnames")
	services = Services()
	runtime = Runtime()
	placement = Placement(default=Placement.default(), missing=Placement.default())

class ApplicationConfiguration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self):
		super(ApplicationConfiguration, self).__init__(ConfigurationSchema())

class TestApplicationConfiguration(unittest.TestCase):
	test_config = """
application:
  name: foo.com
  tags:
    tag: value
  source:
    method: paasmaker.git
    location: git@foo.com/paasmaker/paasmaker.git
    prepare:
      - php composer.phar install

runtime:
  name: PHP
  version: 5.4
  startup:
    - php app/console cache:warm
    - php app/console assets:deploy

hostnames:
  - foo.com
  - foo.com.au
  - www.foo.com.au
  - www.foo.com

services:
  - name: paasmaker.test
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
		config = ApplicationConfiguration()
		config.load(self.test_config)
		self.assertEquals(config.get_flat('runtime.name'), "PHP", "Runtime value is not as expected.")
		self.assertEquals(config.get_flat('runtime.version'), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config['hostnames']), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config['hostnames'], "Hostnames does not contain an expected item.")
		self.assertEquals(len(config['services']), 1, "Services array does not contain the expected number of items.")
		self.assertEquals(config.get_flat('application.name'), "foo.com", "Application name is not as expected.")

	def test_bad_config(self):
		try:
			config = ApplicationConfiguration()
			config.load(self.bad_config)
			self.assertTrue(False, "Should have thrown an exception.")
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Threw exception correctly.")


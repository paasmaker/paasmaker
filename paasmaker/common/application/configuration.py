import unittest
import colander
import yaml
import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationException

# Schema definition.
class Runtime(colander.MappingSchema):
	provider = colander.SchemaNode(colander.String(),
		title="Runtime provider",
		description="Runtime provider symbolic name")
	version = colander.SchemaNode(colander.String(),
		title="Runtime version",
		description="The version of the runtime to use.")
	startup = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()),
		title="Startup commands",
		description="Commands used to prepare the code before starting the instance.",
		default=[],
		missing=[])
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Parameters",
		description="Parameters to the runtime.",
		missing={},
		default={})

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

class Manifest(colander.MappingSchema):
	version = colander.SchemaNode(colander.Integer(),
		title="Manifest version",
		description="The manifest format version number.")

class ConfigurationSchema(colander.MappingSchema):
	application = Application()
	hostnames = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()), title="Hostnames")
	services = Services()
	# TODO: Validate the sub items under here.
	instances = colander.SchemaNode(colander.Mapping(unknown='preserve'))
	placement = Placement(default=Placement.default(), missing=Placement.default())
	manifest = Manifest()

class ApplicationConfiguration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self):
		super(ApplicationConfiguration, self).__init__(ConfigurationSchema())

class TestApplicationConfiguration(unittest.TestCase):
	test_config = """
manifest:
  version: 1

application:
  name: foo.com
  tags:
    tag: value
  source:
    method: paasmaker.scm.git
    location: git@foo.com/paasmaker/paasmaker.git
    prepare:
      - paasmaker.prepare.symfony2
      - php composer.phar install
      - php app/console cache:clear

instances:
  web:
    quantity: 1
    provider: paasmaker.runtime.php
    version: 5.4
    startup:
      - paasmaker.startup.symfony2
      - php app/console cache:warm
      - php app/console assets:deploy

hostnames:
  - foo.com
  - foo.com.au
  - www.foo.com.au
  - www.foo.com

services:
  - name: test
    provider: paasmaker.service.test
    options:
      bar: foo

placement:
  strategy: paasmaker.placement.default
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
		self.assertEquals(config.get_flat('manifest.version'), 1, "Manifest version is incorrect.")
		# Disabled until the schema can be sorted out.
		#self.assertEquals(config.get_flat('instances.web.provider'), "paasmaker.runtime.php", "Runtime provider is not as expected.")
		#self.assertEquals(config.get_flat('instances.web.version'), "5.4", "Runtime version is not as expected.")
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


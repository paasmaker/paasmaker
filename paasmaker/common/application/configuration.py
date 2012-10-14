import unittest
import colander
import yaml
import paasmaker
import tornado
import json
from paasmaker.util.configurationhelper import InvalidConfigurationException
from paasmaker.common.controller import BaseControllerTest

# Schema definition.
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
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})

	@staticmethod
	def default():
		return {'strategy': 'paasmaker.placement.default', 'parameters': {}}

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

class Runtime(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Runtime name",
		description="The runtime plugin name.")
	parameters = colander.SchemaNode(colander.String(),
		title="Runtime parameters",
		description="Any parameters to the runtime.",
		default={},
		missing={})
	version = colander.SchemaNode(colander.String(),
		title="Runtime version",
		description="The requested runtime version.")

class Instance(colander.MappingSchema):
	quantity = colander.SchemaNode(colander.Integer(),
		title="Quantity",
		description="The quantity of instances to start with.",
		missing=1,
		default=1)
	runtime = Runtime()
	startup = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()),
		title="Startup commands",
		description="Commands used to prepare the code before starting the instance.",
		default=[],
		missing=[])
	placement = Placement(default=Placement.default(), missing=Placement.default())
	hostnames = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()), title="Hostnames", default=[], missing=[])

class ConfigurationSchema(colander.MappingSchema):
	application = Application()
	services = Services()
	# TODO: Validate the sub items under here.
	instances = colander.SchemaNode(colander.Mapping(unknown='preserve'))
	manifest = Manifest()

class ApplicationConfiguration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self):
		super(ApplicationConfiguration, self).__init__(ConfigurationSchema())

	def post_load(self):
		# Check the schema of nodes in the instances map.
		# Because there doesn't seem to be a way to get colander to do so.
		schema = Instance()
		for instance in self['instances']:
			try:
				# Validate.
				valid = schema.deserialize(self['instances'][instance])
				# Replace that section in our schema with the data.
				# TODO: This won't update the flat data.
				self['instances'][instance] = valid
			except colander.Invalid, ex:
				# Raise another exception that encapsulates more context.
				# In future this can be used to print a nicer report.
				# Because the default output is rather confusing...!
				raise paasmaker.common.configuration.InvalidConfigurationException(ex, '', self['instance']['instances'])

	def create_application(self, session, workspace):
		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = self.get_flat('application.name')

		return application

	def unpack_into_database(self, session, application):
		# Figure out the new version number.
		new_version_number = paasmaker.model.ApplicationVersion.get_next_version_number(session, application)

		# Create a new version.
		version = paasmaker.model.ApplicationVersion()
		version.manifest = self.raw
		version.application = application
		version.version = new_version_number

		# Import instances.
		for name, imetadata in self['instances'].iteritems():
			instance_type = paasmaker.model.ApplicationInstanceType()

			# Basic information.
			instance_type.name = name
			instance_type.quantity = imetadata['quantity']
			instance_type.state = 'NEW'

			# Runtime information.
			instance_type.runtime_name = imetadata['runtime']['name']
			instance_type.runtime_parameters = json.dumps(imetadata['runtime']['parameters'])
			instance_type.runtime_version = json.dumps(imetadata['runtime']['version'])

			# Placement data.
			instance_type.placement_provider = imetadata['placement']['strategy']
			instance_type.placement_parameters = json.dumps(imetadata['placement']['parameters'])

			# Startup data.
			instance_type.startup = json.dumps(imetadata['startup'])

			# Import hostnames.
			for hostname_raw in imetadata['hostnames']:
				hostname = paasmaker.model.ApplicationInstanceTypeHostname()
				hostname.application_instance_type = instance_type
				hostname.hostname = hostname_raw
				instance_type.hostnames.append(hostname)

			version.instance_types.append(instance_type)

		return version

class TestApplicationConfiguration(BaseControllerTest):
	config_modules = ['pacemaker']

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
    runtime:
      name: paasmaker.runtime.php
      parameters:
        document_root: web
      version: 5.4
    startup:
      - paasmaker.startup.symfony2
      - php app/console cache:warm
      - php app/console assets:deploy
    placement:
      strategy: paasmaker.placement.default
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
"""

	bad_config = """
"""

	def setUp(self):
		super(TestApplicationConfiguration, self).setUp()

	def tearDown(self):
		super(TestApplicationConfiguration, self).tearDown()

	def get_app(self):
		self.late_init_configuration()
		routes = []
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_loading(self):
		config = ApplicationConfiguration()
		config.load(self.test_config)
		self.assertEquals(config.get_flat('manifest.version'), 1, "Manifest version is incorrect.")
		# Disabled until the schema can be sorted out.
		#self.assertEquals(config.get_flat('instances.web.provider'), "paasmaker.runtime.php", "Runtime provider is not as expected.")
		#self.assertEquals(config.get_flat('instances.web.version'), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config['instances']['web']['hostnames']), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config['instances']['web']['hostnames'], "Hostnames does not contain an expected item.")
		self.assertEquals(len(config['services']), 1, "Services array does not contain the expected number of items.")
		self.assertEquals(config.get_flat('application.name'), "foo.com", "Application name is not as expected.")

	def test_bad_config(self):
		try:
			config = ApplicationConfiguration()
			config.load(self.bad_config)
			self.assertTrue(False, "Should have thrown an exception.")
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Threw exception correctly.")

	def test_unpack_configuration(self):
		config = ApplicationConfiguration()
		config.load(self.test_config)

		session = self.configuration.get_database_session()

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		session.add(workspace)
		session.commit()

		application = config.create_application(session, workspace)
		version = config.unpack_into_database(session, application)

		session.add(application)
		session.add(version)
		session.commit()

		session.refresh(application)
		session.refresh(version)

		self.assertEquals(application.name, 'foo.com', 'Application name is not as expected.')
		self.assertEquals(len(version.instance_types[0].hostnames), 4, "Unexpected number of hostnames.")
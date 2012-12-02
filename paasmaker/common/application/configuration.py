
import re
import json

import colander
import yaml
import paasmaker
import tornado

from paasmaker.util.configurationhelper import InvalidConfigurationException
from paasmaker.common.controller import BaseControllerTest

from paasmaker.common.core import constants

# Validation constants.
# Identifiers, like application and service names.
VALID_IDENTIFIER = re.compile("[-A-Za-z0-9.]{1,}")
VALID_PLUGIN_NAME = re.compile("[-a-z0-9.]")

# Schema definition.
class Service(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Service name",
		description="Your name for the service to identify it",
		validator=colander.Regex(VALID_IDENTIFIER, "Service names must match " + VALID_IDENTIFIER.pattern))
	provider = colander.SchemaNode(colander.String(),
		title="Provider name",
		description="Provider symbolic name",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})

class Services(colander.SequenceSchema):
	service = Service(unknown='preserve')

class Placement(colander.MappingSchema):
	strategy = colander.SchemaNode(colander.String(),
		title="Placement strategy",
		description="The placement strategy to use",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})

	@staticmethod
	def default():
		return {'strategy': 'paasmaker.placement.default', 'parameters': {}}

class Runtime(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Runtime name",
		description="The runtime plugin name.",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Runtime parameters",
		description="Any parameters to the runtime.",
		default={},
		missing={})
	version = colander.SchemaNode(colander.String(),
		title="Runtime version",
		description="The requested runtime version.")

class PrepareCommand(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String(),
		title="Plugin name",
		description="The plugin to be used for this prepare action.",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Plugin Parameters",
		description="Parameters for this particular plugin",
		missing={},
		default={})

class Prepares(colander.SequenceSchema):
	command = PrepareCommand()

class PrepareSection(colander.MappingSchema):
	commands = Prepares(missing=[], default=[])
	runtime = Runtime(missing={'name': None}, default={'name': None})

	@staticmethod
	def default():
		return {'commands': [], 'runtime': {'name': None}}

class ApplicationSource(colander.MappingSchema):
	method = colander.SchemaNode(colander.String(),
		title="Source fetching method",
		description="The method to grab and prepare the source",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Parameters for the source fetcher.",
		description="Any parameters to the source fetching method.",
		default={},
		missing={})
	prepare = PrepareSection(default=PrepareSection.default(), missing=PrepareSection.default())

class Application(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Application name",
		decription="The name of the application",
		validator=colander.Regex(VALID_IDENTIFIER, "Application names must match " + VALID_IDENTIFIER.pattern))
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'), missing={}, default={})
	source = ApplicationSource()

class Cron(colander.MappingSchema):
	# TODO: Place an epic regex on this field to validate it.
	runspec = colander.SchemaNode(colander.String(),
		title="Run specification",
		description="CRON-style time specification syntax.")
	uri = colander.SchemaNode(colander.String(),
		title="URI for script",
		descripton="The URI for the appropriate cron script.")
	username = colander.SchemaNode(colander.String(),
		title="Authentication Username",
		description="The HTTP basic authentication username, if the script requires it.",
		default=None,
		missing=None)
	password = colander.SchemaNode(colander.String(),
		title="Authentication Password",
		description="The HTTP basic authentication password, if the script requires it.",
		default=None,
		missing=None)

class Crons(colander.SequenceSchema):
	crons = Cron()

class Manifest(colander.MappingSchema):
	format = colander.SchemaNode(colander.Integer(),
		title="Manifest format",
		description="The manifest format version number.")

class Instance(colander.MappingSchema):
	quantity = colander.SchemaNode(colander.Integer(),
		title="Quantity",
		description="The quantity of instances to start with.",
		missing=1,
		default=1)
	runtime = Runtime()
	startup = Prepares(default=[], missing=[])
	placement = Placement(default=Placement.default(), missing=Placement.default())
	hostnames = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()), title="Hostnames", default=[], missing=[])
	exclusive = colander.SchemaNode(colander.Boolean(),
		title="Version Exclusive",
		description="If set to true, only one version of this instance type will run at a time. This is good for background workers that you don't want overlapping.",
		default=False,
		missing=False)
	standalone = colander.SchemaNode(colander.Boolean(),
		title="Standalone",
		description="If true, this instance doesn't require a TCP port. Affects the startup of the application.",
		default=False,
		missing=False)
	crons = Crons(default=[], missing=[])

class ConfigurationSchema(colander.MappingSchema):
	application = Application()
	services = Services()
	# NOTE: We validate the instances ApplicationConfiguration.post_load(), because
	# there didn't seem to be an easy way to get Colander to validate them.
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

	def set_upload_location(self, location):
		self['application']['source']['parameters']['location'] = location

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
			instance_type.state = constants.INSTANCE_TYPE.NEW
			instance_type.exclusive = imetadata['exclusive']
			instance_type.standalone = imetadata['standalone']

			# Runtime information.
			instance_type.runtime_name = imetadata['runtime']['name']
			instance_type.runtime_parameters = imetadata['runtime']['parameters']
			instance_type.runtime_version = imetadata['runtime']['version']

			# Placement data.
			instance_type.placement_provider = imetadata['placement']['strategy']
			instance_type.placement_parameters = imetadata['placement']['parameters']

			# Startup data.
			instance_type.startup = imetadata['startup']

			# Import hostnames.
			for hostname_raw in imetadata['hostnames']:
				hostname = paasmaker.model.ApplicationInstanceTypeHostname()
				hostname.application_instance_type = instance_type
				hostname.hostname = hostname_raw
				instance_type.hostnames.append(hostname)

			# Import crons.
			for cron_raw in imetadata['crons']:
				cron = paasmaker.model.ApplicationInstanceTypeCron()
				cron.application_instance_type = instance_type
				cron.runspec = cron_raw['runspec']
				cron.uri = cron_raw['uri']
				cron.username = cron_raw['username']
				cron.password = cron_raw['password']

			version.instance_types.append(instance_type)

		# Import and link services.
		for servicemeta in self['services']:
			# Create or fetch the service.
			service = paasmaker.model.Service.get_or_create(session, application.workspace, servicemeta['name'])
			service.provider = servicemeta['provider']
			service.parameters = servicemeta['parameters']

			version.services.append(service)

		return version

class TestApplicationConfiguration(BaseControllerTest):
	config_modules = ['pacemaker']

	test_config = """
manifest:
  format: 1

application:
  name: foo.com
  tags:
    tag: value
  source:
    method: paasmaker.scm.git
    parameters:
      location: git@foo.com/paasmaker/paasmaker.git
    prepare:
      runtime:
        name: paasmaker.runtime.shell
        version: 1
      commands:
        - plugin: paasmaker.prepare.symfony2
        - plugin: paasmaker.prepare.shell
          parameters:
            commands:
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
      - plugin: paasmaker.prepare.shell
        parameters:
          commands:
            - php app/console cache:warm
            - php app/console assets:deploy
    placement:
      strategy: paasmaker.placement.default
    hostnames:
      - foo.com
      - foo.com.au
      - www.foo.com.au
      - www.foo.com
    crons:
      - runspec: '* * * * *'
        uri: /test
      - runspec: '* * * * *'
        uri: /test/bar
        username: test
        password: test

services:
  - name: test
    provider: paasmaker.service.test
    parameters:
      bar: foo
  - name: test-two
    provider: paasmaker.service.test
    parameters:
      bar: foo
"""

	bad_config = """
"""

	def setUp(self):
		super(TestApplicationConfiguration, self).setUp()

	def tearDown(self):
		super(TestApplicationConfiguration, self).tearDown()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = []
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_loading(self):
		config = ApplicationConfiguration()
		config.load(self.test_config)
		self.assertEquals(config.get_flat('manifest.format'), 1, "Manifest version is incorrect.")
		# Disabled until the schema can be sorted out.
		#self.assertEquals(config.get_flat('instances.web.provider'), "paasmaker.runtime.php", "Runtime provider is not as expected.")
		#self.assertEquals(config.get_flat('instances.web.version'), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config['instances']['web']['hostnames']), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config['instances']['web']['hostnames'], "Hostnames does not contain an expected item.")
		self.assertEquals(len(config['services']), 2, "Services array does not contain the expected number of items.")
		self.assertEquals(config.get_flat('application.name'), "foo.com", "Application name is not as expected.")
		self.assertEquals(len(config['instances']['web']['crons']), 2, "Number of crons is not as expected.")

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
		workspace.stub = 'test'
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
		self.assertEquals(len(version.services), 2, "Unexpected number of services.")
		self.assertEquals(len(version.services[0].parameters), 1, "Unexpected number of keys in the services parameters.")
		self.assertEquals(len(version.instance_types[0].crons), 2, "Unexpected number of crons.")

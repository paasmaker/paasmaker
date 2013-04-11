#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import re
import json

import colander
import yaml
import paasmaker
import tornado

from paasmaker.util.configurationhelper import InvalidConfigurationParameterException
from paasmaker.util.configurationhelper import InvalidConfigurationFormatException
from paasmaker.util.configurationhelper import StrictAboutExtraKeysColanderMappingSchema
from paasmaker.common.controller import BaseControllerTest
from paasmaker.util.plugin import MODE

from paasmaker.common.core import constants

# Validation constants.
# Identifiers, like application and service names.
# Underscores are not permitted in identifiers, as they appear in DNS hostnames.
VALID_IDENTIFIER = re.compile(r"^[-A-Za-z0-9.]{1,}$")
VALID_PLUGIN_NAME = re.compile(r"^[-a-z0-9._]{1,}$")

# Schema definition.
class Plugin(StrictAboutExtraKeysColanderMappingSchema):
	name = colander.SchemaNode(
		colander.String(),
		title="Plugin name",
		description="Descriptive name for this plugin (to identify it in the web console)",
		missing='', default='',
		validator=colander.Regex(VALID_IDENTIFIER, "Plugin name must match " + VALID_IDENTIFIER.pattern)
	)
	plugin = colander.SchemaNode(
		colander.String(),
		title="Symbolic plugin name",
		description="Symbolic name of this plugin, as defined in the main paasmaker options file",
		validator=colander.Regex(VALID_PLUGIN_NAME, "Plugin name must match " + VALID_PLUGIN_NAME.pattern)
	)
	parameters = colander.SchemaNode(
		colander.Mapping(unknown='preserve'),
		missing={},
		default={}
	)

class ServicePlugin(Plugin):
	# Service definitions are identical to normal plugins, except that the
	# name field is required (as well as the plugin field)
	name = colander.SchemaNode(
		colander.String(),
		title="Service name",
		description="Your name for the service to identify it",
		validator=colander.Regex(VALID_IDENTIFIER, "Service names must match " + VALID_IDENTIFIER.pattern)
	)

class RuntimePlugin(Plugin):
	# Runtime plugins have a required version field.
	version = colander.SchemaNode(
		colander.String(),
		title="Runtime version",
		description="The requested runtime version."
	)

class PlacementPlugin(Plugin):
	# Placement plugin doesn't have to be defined; just use the default if it isn't.
	@staticmethod
	def default():
		return {'plugin': 'paasmaker.placement.default', 'parameters': {}}

class Services(colander.SequenceSchema):
	service = ServicePlugin()

class Prepares(colander.SequenceSchema):
	command = Plugin()

class PrepareSection(StrictAboutExtraKeysColanderMappingSchema):
	commands = Prepares(
		missing=[],
		default=[]
	)
	runtime = RuntimePlugin(
		missing={'plugin': None},
		default={'plugin': None}
	)

	@staticmethod
	def default():
		return {'commands': [], 'runtime': {'plugin': None}}

class Application(StrictAboutExtraKeysColanderMappingSchema):
	name = colander.SchemaNode(
		colander.String(),
		title="Application name",
		decription="The name of the application",
		validator=colander.Regex(VALID_IDENTIFIER, "Application names must match " + VALID_IDENTIFIER.pattern)
	)
	tags = colander.SchemaNode(
		colander.Mapping(unknown='preserve'),
		missing={},
		default={}
	)
	prepare = PrepareSection(
		default=PrepareSection.default(),
		missing=PrepareSection.default()
	)

class Cron(StrictAboutExtraKeysColanderMappingSchema):
	# TODO: Place an epic regex on this field to validate it.
	runspec = colander.SchemaNode(
		colander.String(),
		title="Run specification",
		description="CRON-style time specification syntax."
	)
	uri = colander.SchemaNode(
		colander.String(),
		title="URI for script",
		descripton="The URI for the appropriate cron script."
	)
	username = colander.SchemaNode(
		colander.String(),
		title="Authentication Username",
		description="The HTTP basic authentication username, if the script requires it.",
		default=None,
		missing=None
	)
	password = colander.SchemaNode(
		colander.String(),
		title="Authentication Password",
		description="The HTTP basic authentication password, if the script requires it.",
		default=None,
		missing=None
	)

class Crons(colander.SequenceSchema):
	crons = Cron()

class Manifest(StrictAboutExtraKeysColanderMappingSchema):
	format = colander.SchemaNode(
		colander.Integer(),
		title="Manifest format",
		description="The manifest format version number."
	)

class Instance(StrictAboutExtraKeysColanderMappingSchema):
	name = colander.SchemaNode(
		colander.String(),
		title="Name",
		description="Instance type name for this instance."
	)
	quantity = colander.SchemaNode(
		colander.Integer(),
		title="Quantity",
		description="The quantity of instances to start with.",
		missing=1,
		default=1
	)
	runtime = RuntimePlugin(
		title="Runtime",
		description="A section describing the runtime plugin name and version for this instance."
	)
	startup = Prepares(
		title="Startup tasks",
		description="A list of plugins and parameters to run on instance startup.",
		default=[],
		missing=[]
	)
	placement = PlacementPlugin(
		title="Placement information",
		description="A section that provides hints to Paasmaker about where to place your application.",
		default=PlacementPlugin.default(),
		missing=PlacementPlugin.default()
	)
	hostnames = colander.SchemaNode(
		colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Hostnames",
		description="A set of public hostnames that this instance will have if it is the current version of the application.",
		default=[],
		missing=[]
	)
	exclusive = colander.SchemaNode(
		colander.Boolean(),
		title="Version Exclusive",
		description="If set to true, only one version of this instance type will run at a time. This is good for background workers that you don't want overlapping.",
		default=False,
		missing=False)
	standalone = colander.SchemaNode(
		colander.Boolean(),
		title="Standalone",
		description="If true, this instance doesn't require a TCP port. Affects the startup of the application.",
		default=False,
		missing=False)
	crons = Crons(
		title="Cron tasks",
		description="A list of cron tasks to run against your instances. Cron is implemented by calling a URL on your instance.",
		default=[], missing=[]
	)

class Instances(colander.SequenceSchema):
	instance = Instance()

class ConfigurationSchema(StrictAboutExtraKeysColanderMappingSchema):
	application = Application()
	services = Services(default=[], missing=[])
	instances = Instances()
	manifest = Manifest()

class ApplicationConfiguration(paasmaker.util.configurationhelper.ConfigurationHelper):
	"""
	A class to load, validate, and work with application manifest files.

	This is a subclass of ``ConfigurationHelper`` which provides some helpers
	when working with the application schemas.
	"""

	def __init__(self, configuration):
		self.configuration = configuration
		super(ApplicationConfiguration, self).__init__(ConfigurationSchema())

	def post_load(self):
		error_list = []

		if self.get_flat("application.prepare.runtime.plugin") is not None:
			error_list.extend(
				self.check_plugin_exists("application.prepare.runtime.plugin", MODE.RUNTIME_ENVIRONMENT)
			)

		if len(self["application"]["prepare"]["commands"]) > 0:
			for i in range(len(self["application"]["prepare"]["commands"])):
				error_list.extend(
					self.check_plugin_exists("application.prepare.commands.%d.plugin" % i, MODE.PREPARE_COMMAND)
				)

		seen_instance_names = {}
		for i in range(len(self["instances"])):
			instance_data = self['instances'][i]

			if instance_data['name'] in seen_instance_names:
				# Duplicated.
				error_list.append(["Instance type %s appears more than once in the manifest file. Each instance type requires a unique name." % instance_data['name']])

			seen_instance_names[instance_data['name']] = True

			error_list.extend(
				self.check_plugin_exists("instances.%d.runtime.plugin" % i, MODE.RUNTIME_EXECUTE)
			)
			error_list.extend(
				self.check_plugin_exists("instances.%d.placement.plugin" % i, MODE.PLACEMENT)
			)
			if len(instance_data["startup"]) > 0:
				for j in range(len(instance_data["startup"])):
					error_list.extend(
						self.check_plugin_exists("instances.%d.startup.%d.plugin" % (i, j), MODE.RUNTIME_STARTUP)
					)

		seen_service_names = {}
		for i in range(len(self["services"])):
			service_data = self['services'][i]

			if service_data['name'] in seen_service_names:
				# Duplicated.
				error_list.append(["Service %s appears more than once in the manifest file. Each service requires a unique name." % service_data['name']])

			seen_service_names[service_data['name']] = True

			error_list.extend(
				self.check_plugin_exists("services.%d.plugin" % i, MODE.SERVICE_CREATE)
			)

		if len(error_list) > 0:
			raise InvalidConfigurationParameterException(str(error_list))

	def check_plugin_exists(self, config_item, mode):
		plugin_name = self.get_flat(config_item)
		if not self.configuration.plugins.exists(plugin_name, mode):
			return ["Plugin %s not enabled or doesn't exist (referenced in %s)" % (plugin_name, config_item)]
		else:
			return []

	def create_application(self, session, workspace):
		"""
		Create a new application, based on this manifest,
		in the given workspace.

		The new Application object is returned. Nothing is saved
		or committed - you will need to add it to the session
		yourself.

		:arg Session session: The session to work in.
		:arg Workspace workspace: The workspace to attach
			the application to.
		"""
		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = self.get_flat('application.name')

		return application

	def unpack_into_database(self, session, application, scm_name, scm_parameters):
		"""
		Unpack a new version of the application into the database.

		This generates all the relevant ORM objects for a new
		version of the supplied application, based on the settings
		contained in the manifest.

		:arg Session session: The session to work in.
		:arg Application application: The application to make a new
			version of.
		:arg str scm_name: The name of the SCM plugin - this is
			simply recorded and not otherwise used.
		:arg dict scm_parameters: The SCM parameters. This is simply
			stored in the new version data.
		"""
		# Figure out the new version number.
		new_version_number = paasmaker.model.ApplicationVersion.get_next_version_number(session, application)

		# Create a new version.
		version = paasmaker.model.ApplicationVersion()
		version.manifest = self.raw
		version.application = application
		version.version = new_version_number
		version.state = constants.VERSION.NEW
		version.scm_name = scm_name
		version.scm_parameters = scm_parameters

		# Import instances.
		for imetadata in self['instances']:
			instance_type = paasmaker.model.ApplicationInstanceType()

			# Basic information.
			instance_type.name = imetadata['name']
			instance_type.quantity = imetadata['quantity']
			instance_type.exclusive = imetadata['exclusive']
			instance_type.standalone = imetadata['standalone']

			# Runtime information.
			instance_type.runtime_name = imetadata['runtime']['plugin']
			instance_type.runtime_parameters = imetadata['runtime']['parameters']
			instance_type.runtime_version = imetadata['runtime']['version']

			# Placement data.
			instance_type.placement_provider = imetadata['placement']['plugin']
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
			service = paasmaker.model.Service.get_or_create(
				session,
				application,
				servicemeta['name']
			)
			service.provider = servicemeta['plugin']
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
  prepare:
    runtime:
      plugin: paasmaker.runtime.shell
      version: 1
    commands:
      - plugin: paasmaker.prepare.shell
        parameters:
          commands:
            - php composer.phar install
            - php app/console cache:clear

instances:
  - name: web
    quantity: 1
    runtime:
      plugin: paasmaker.runtime.php
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
      plugin: paasmaker.placement.default
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
    plugin: paasmaker.service.test
    parameters:
      bar: foo
  - name: test-two
    plugin: paasmaker.service.test
    parameters:
      bar: foo
"""

	invalid_plugin_config = """
manifest:
  format: 1

application:
  name: foobar.com
  prepare:
    runtime:
      plugin: paasmaker.runtime.lalala_notlistening
      version: 1

instances:
  - name: web
    runtime:
      plugin: paasmaker.runtime.zomg_what_plugin_is_this
      version: 1

services:
  - name: busted
    plugin: paasmaker.service.icantbelieveitsnot_aplugin
"""

	empty_config = """
"""

	duplicated_services_instances = """
manifest:
  format: 1

application:
  name: foobar.com
  prepare:
    runtime:
      plugin: paasmaker.runtime.lalala_notlistening
      version: 1

instances:
  - name: web
    quantity: 1
    runtime:
      plugin: paasmaker.runtime.php
      parameters:
        document_root: web
      version: 5.4
  - name: web
    quantity: 1
    runtime:
      plugin: paasmaker.runtime.php
      parameters:
        document_root: web
      version: 5.4

services:
  - name: test
    plugin: paasmaker.service.test
    parameters:
      bar: foo
  - name: test
    plugin: paasmaker.service.test
    parameters:
      bar: foo
"""

	def setUp(self):
		super(TestApplicationConfiguration, self).setUp()

		# Register our test plugin
		self.configuration.plugins.register(
			'paasmaker.service.test',
			'paasmaker.common.testplugin.TestPlugin',
			{},
			'Dummy service plugin'
		)

	def tearDown(self):
		super(TestApplicationConfiguration, self).tearDown()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = []
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_loading(self):
		config = ApplicationConfiguration(self.configuration)
		config.load(self.test_config)
		self.assertEquals(config.get_flat('manifest.format'), 1, "Manifest version is incorrect.")
		# Disabled until the schema can be sorted out.
		#self.assertEquals(config.get_flat('instances[0].provider'), "paasmaker.runtime.php", "Runtime provider is not as expected.")
		#self.assertEquals(config.get_flat('instances[0].version'), "5.4", "Runtime version is not as expected.")
		self.assertEquals(len(config['instances'][0]['hostnames']), 4, "Number of hostnames is not as expected.")
		self.assertIn("www.foo.com.au", config['instances'][0]['hostnames'], "Hostnames does not contain an expected item.")
		self.assertEquals(len(config['services']), 2, "Services array does not contain the expected number of items.")
		self.assertEquals(config.get_flat('application.name'), "foo.com", "Application name is not as expected.")
		self.assertEquals(len(config['instances'][0]['crons']), 2, "Number of crons is not as expected.")

	def test_empty_config(self):
		try:
			config = ApplicationConfiguration(self.configuration)
			config.load(self.empty_config)
			self.assertTrue(False, "Should have thrown an exception.")
		except InvalidConfigurationFormatException, ex:
			self.assertTrue(True, "Threw exception correctly.")

	def test_invalid_plugin_config(self):
		try:
			config = ApplicationConfiguration(self.configuration)
			config.load(self.invalid_plugin_config)
			self.assertTrue(False, "Invalid plugin config should have thrown an exception.")
		except InvalidConfigurationParameterException, ex:
			self.assertIn(
				"Plugin paasmaker.runtime.lalala_notlistening not enabled or doesn't exist (referenced in application.prepare.runtime.plugin)",
				ex.message, "Invalid plugin config threw an exception without the expected error message"
			)
			self.assertIn(
				"Plugin paasmaker.runtime.zomg_what_plugin_is_this not enabled or doesn't exist (referenced in instances.0.runtime.plugin)",
				ex.message, "Invalid plugin config threw an exception without the expected error message"
			)
			self.assertIn(
				"Plugin paasmaker.service.icantbelieveitsnot_aplugin not enabled or doesn't exist (referenced in services.0.plugin)",
				ex.message, "Invalid plugin config threw an exception without the expected error message"
			)

	def test_duplicated_instance_service_config(self):
		try:
			config = ApplicationConfiguration(self.configuration)
			config.load(self.duplicated_services_instances)
			self.assertTrue(False, "Invalid plugin config should have thrown an exception.")
		except InvalidConfigurationParameterException, ex:
			self.assertIn(
				"Service test appears more than once in the manifest file. Each service requires a unique name.",
				ex.message, "Duplicated services did not cause an error."
			)
			self.assertIn(
				"Instance type web appears more than once in the manifest file. Each instance type requires a unique name.",
				ex.message, "Duplicated instance types did not cause an error."
			)

	def test_unpack_configuration(self):
		config = ApplicationConfiguration(self.configuration)
		config.load(self.test_config)

		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'
		session.add(workspace)
		session.commit()

		application = config.create_application(session, workspace)
		version = config.unpack_into_database(session, application, 'paasmaker.scm.zip', {'foo': 'bar'})

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
		self.assertEquals(version.scm_name, 'paasmaker.scm.zip', "Did not store the SCM name.")
		self.assertEquals(version.scm_parameters['foo'], 'bar', "Did not store the SCM parameters.")

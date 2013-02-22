
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE
from ...testhelpers import TestHelpers

import tornado
from pubsub import pub

import colander

class SelectLocationsJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class SelectLocationsJob(BaseJob):
	"""
	A job to select instance locations for a given application version.

	This job will use the appropriate placement algorithm for that application
	to place instances, and will only allocate new instances to meet the correct
	number for an application. If there are too many instances, no action
	will be taken - other parts of Paasmaker handle this case.
	"""
	MODES = {
		MODE.JOB: SelectLocationsJobParametersSchema()
	}

	def start_job(self, context):
		self.logger.info("Starting to select locations.")

		self.session = self.configuration.get_database_session()
		self.instance_type = self.session.query(
			paasmaker.model.ApplicationInstanceType
		).get(self.parameters['application_instance_type_id'])

		# Fire up the plugin for placement.
		plugin_exists = self.configuration.plugins.exists(
			self.instance_type.placement_provider,
			paasmaker.util.plugin.MODE.PLACEMENT
		)
		if not plugin_exists:
			error_message = "No placement provider %s" % self.instance_type.placement_provider
			self.logger.error(error_message)
			self.failed(error_message)
		else:
			placement = self.configuration.plugins.instantiate(
				self.instance_type.placement_provider,
				paasmaker.util.plugin.MODE.PLACEMENT,
				self.instance_type.placement_parameters,
				self.logger
			)

			adjustment_quantity = self.instance_type.adjustment_instances(self.session)

			if adjustment_quantity == 0:
				finish_message = "No more instances required. No action taken."
				self.logger.info(finish_message)
				self.success({}, finish_message)
			elif adjustment_quantity < 0:
				# We have too many instances.
				finish_message = "We have too many instances. No action will be taken at this time."
				self.logger.warning(finish_message)
				self.success({}, finish_message)
			else:
				# Get it to choose the number of instances that we want.
				# This will call us back when ready.
				placement.choose(
					self.session,
					self.instance_type,
					adjustment_quantity,
					self.select_success,
					self.select_failure
				)

	def select_success(self, nodes, message):
		# Ok, now that we have a chosen set of nodes, create records for them in
		# our database.
		for node in nodes:
			instance = paasmaker.model.ApplicationInstance()
			instance.application_instance_type = self.instance_type
			instance.node = node
			instance.state = constants.INSTANCE.ALLOCATED
			instance.instance_id = str(uuid.uuid4())

			self.session.add(instance)

		self.session.commit()

		self.success({}, "Successfully chosen %d nodes for this instance." % len(nodes))

	def select_failure(self, message):
		self.failed("Failed to find nodes for this instance: " + message)

class SelectLocationsJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(SelectLocationsJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(SelectLocationsJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def create_sample_application(self, session, runtime_name, runtime_parameters, runtime_version):
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''
		application_version.state = constants.VERSION.PREPARED
		application_version.scm_name = 'paasmaker.scm.zip'
		application_version.scm_parameters = {}

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = runtime_name
		instance_type.runtime_parameters = runtime_parameters
		instance_type.runtime_version = runtime_version
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.standalone = False

		session.add(instance_type)
		session.commit()

		return instance_type

	def test_simple_success(self):
		# Set up the environment.
		s = self.configuration.get_database_session()
		instance_type = self.create_sample_application(s, 'paasmaker.runtime.php', {}, '5.3')

		node = self.add_simple_node(s, {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.php': ['5.3', '5.3.10']
			}
		}, self.configuration)

		# Register the default placement provider.
		self.configuration.plugins.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)

		self.configuration.job_manager.add_job(
			'paasmaker.job.coordinate.selectlocations',
			{'application_instance_type_id': instance_type.id},
			"Select locations for %s" % instance_type.name,
			self.stop
		)

		job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(job_id, self.stop)
		self.wait()

		result = self.wait()
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Verify that we got what we wanted.
		instances = s.query(paasmaker.model.ApplicationInstance)
		for instance in instances:
			self.assertEquals(instance.state, constants.INSTANCE.ALLOCATED, "Instance is not in correct state.")
			self.assertEquals(instance.application_instance_type.id, instance_type.id, "Instance is not for our application.")

	def test_simple_failed(self):
		# Set up the environment.
		s = self.configuration.get_database_session()
		instance_type = self.create_sample_application(s, 'paasmaker.runtime.php', {}, '5.3')

		node = self.add_simple_node(s, {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.shell': ['1']
			}
		}, self.configuration)

		# Register the default placement provider.
		self.configuration.plugins.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)

		self.configuration.job_manager.add_job(
			'paasmaker.job.coordinate.selectlocations',
			{'application_instance_type_id': instance_type.id},
			"Select locations for %s" % instance_type.name,
			self.stop
		)

		job_id = self.wait()
		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(job_id, self.stop)
		self.wait()

		result = self.wait()
		while result.state != constants.JOB.FAILED:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.FAILED, "Should have failed.")
		# TODO: Make sure it failed for the advertised reason.

import uuid

import paasmaker
from paasmaker.common.core import constants

import tornado
from pubsub import pub

class SelectLocationsJob(paasmaker.util.jobmanager.JobRunner):

	def __init__(self, configuration, session, instance_type):
		self.configuration = configuration
		self.session = session
		self.instance_type = instance_type

	def get_job_title(self):
		params = (self.instance_type.application_version.application.name,
			self.instance_type.application_version.version,
			self.instance_type.name)
		return "Select run locations for %s (v%d, type %s)" % params

	def start_job(self):
		logger = self.job_logger()
		logger.info("Starting to select locations.")

		# Fire up the plugin for placement.
		if not self.configuration.plugins.exists(self.instance_type.placement_provider, paasmaker.util.plugin.MODE.PLACEMENT):
			self.finished_job(constants.JOB.FAILED, "No placement provider %s" % self.instance_type.placement_provider)
		else:
			placement = self.configuration.plugins.instantiate(
				self.instance_type.placement_provider,
				paasmaker.util.plugin.MODE.PLACEMENT,
				self.instance_type.placement_parameters,
				logger
			)

			# Get it to choose the number of instances that we want.
			# This will call us back when ready.
			placement.choose(self.session, self.instance_type, self.instance_type.quantity, self.success, self.failure)

	def success(self, nodes, message):
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

		self.finished_job(constants.JOB.SUCCESS, "Successfully chosen nodes for this instance. " + message)

	def failure(self, message):
		self.finished_job(constants.JOB.FAILED, "Failed to find any nodes to run this instance: " + message)

class SelectLocationsJobTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(SelectLocationsJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(SelectLocationsJobTest, self).tearDown()

	def on_job_status(self, message):
		self.stop(message)

	def on_job_catchall(self, message):
		# This is for debugging.
		#print str(message.flatten())
		pass

	def on_audit_catchall(self, message):
		# This is for debugging.
		#print str(message.flatten())
		pass

	def create_sample_application(self, session, runtime_name, runtime_parameters, runtime_version):
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''

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
		instance_type.state = constants.INSTANCE_TYPE.PREPARED

		session.add(instance_type)
		session.commit()

		return instance_type

	def add_simple_node(self, session, tags):
		ctr = 1
		node = paasmaker.model.Node(name='test%d' % ctr,
				route='%d.test.paasmaker.com' % ctr,
				apiport=888,
				uuid='%s-uuid' % ctr,
				state=constants.NODE.ACTIVE)
		node.heart = True
		node.tags = tags
		session.add(node)
		session.commit()

		return node

	def test_simple_success(self):
		# Set up the environment.
		s = self.configuration.get_database_session()
		instance_type = self.create_sample_application(s, 'paasmaker.runtime.php', {}, '5.3')

		node = self.add_simple_node(s, {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.php': ['5.3', '5.3.10']
			}
		})

		# Register the default placement provider.
		self.configuration.plugins.register('paasmaker.placement.default', 'paasmaker.pacemaker.placement.default.DefaultPlacement', {})

		select_job = SelectLocationsJob(self.configuration, s, instance_type)
		self.configuration.job_manager.add_job(select_job)
		select_job_id = select_job.job_id

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(select_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')
		pub.subscribe(self.on_audit_catchall, 'job.audit')

		# And make it work.
		self.configuration.job_manager.evaluate()

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
		})

		# Register the default placement provider.
		self.configuration.plugins.register('paasmaker.placement.default', 'paasmaker.pacemaker.placement.default.DefaultPlacement', {})

		select_job = SelectLocationsJob(self.configuration, s, instance_type)
		self.configuration.job_manager.add_job(select_job)
		select_job_id = select_job.job_id

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(select_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')

		# And make it work.
		self.configuration.job_manager.evaluate()

		result = self.wait()

		self.assertEquals(result.state, constants.JOB.FAILED, "Should have failed.")
		# TODO: Make sure it failed for the advertised reason.
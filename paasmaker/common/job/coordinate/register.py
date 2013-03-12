
import os
import subprocess
import uuid
import socket

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from startup import StartupRootJob
from shutdown import ShutdownRootJob
from deregister import DeRegisterRootJob
from instancerootbase import InstanceRootBase
from current import CurrentVersionRequestJob
from paasmaker.util.plugin import MODE

import tornado
from pubsub import pub
import colander
import sqlalchemy

# TODO: Implement abort features for all of these jobs.

# What is this job and related jobs doing?
# The tree ends up like this:
# - Root (Contains all other jobs)
#   - Register request queuer (this creates more jobs to let nodes know what they need to do)
#     - Select locations (this job chooses locations for jobs)
#   - Register Instance A on Node A (dynamically added)
#   - Register Instance B on Node B (dynamically added)
#   - ... and so forth.

class RegisterRootJob(InstanceRootBase):
	"""
	A job to set up registration requests for instances.

	NOTE: This job is just a container that submits other jobs to actually
	register the instances.
	"""

	@classmethod
	def setup_version(cls, configuration, application_version, callback, error_callback, limit_instances=None, parent=None):
		# List all the instance types.
		# Assume we have an open session on the application_version object.

		context = {}
		context['application_version_id'] = application_version.id

		if limit_instances:
			context['limit_instances'] = limit_instances

		tags = []
		tags.append('workspace:%d' % application_version.application.workspace.id)
		tags.append('application:%d' % application_version.application.id)
		tags.append('application_version:%d' % application_version.id)

		# The root of this tree.
		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.coordinate.registerroot',
			{},
			"Select locations and register instances for %s version %d" % (application_version.application.name, application_version.version),
			context=context,
			tags=tags
		)

		for instance_type in application_version.instance_types:
			parameters = {}
			parameters['application_instance_type_id'] = instance_type.id

			# The tag gets added here, but it's actually tagged on the root job.
			type_tags = ['application_instance_type:%d' % instance_type.id]

			registerer = tree.add_child()
			registerer.set_job(
				'paasmaker.job.coordinate.registerrequest',
				parameters,
				"Registration requests for %s" % instance_type.name,
				tags=type_tags
			)

			selectlocations = registerer.add_child()
			selectlocations.set_job(
				'paasmaker.job.coordinate.selectlocations',
				parameters,
				"Select instance locations for %s" % instance_type.name,
			)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added, parent=parent)

	def start_job(self, context):
		def version_updated():
			self.logger.info("Select locations and register instances.")
			self.success({}, "Selected and registered instances.")

		self.update_version_from_context(context, constants.VERSION.READY, version_updated)

class RegisterRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class RegisterRequestJob(BaseJob):
	"""
	A job to submit more jobs on actual heart nodes to register instances.
	"""
	MODES = {
		MODE.JOB: RegisterRequestJobParametersSchema()
	}

	def start_job(self, context):
		self.logger.info("Creating node registration jobs.")

		def got_session(session):
			instance_type = session.query(
				paasmaker.model.ApplicationInstanceType
			).get(self.parameters['application_instance_type_id'])

			# Find all instances that need to be registered.
			# Attempt to grab all the data at once that is required.
			to_allocate = session.query(
				paasmaker.model.ApplicationInstance
			).options(
				sqlalchemy.orm.joinedload(
					paasmaker.model.ApplicationInstance.node
				)
			).filter(
				paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
				paasmaker.model.ApplicationInstance.state == constants.INSTANCE.ALLOCATED
			)

			# Now set up the jobs.
			container = self.configuration.job_manager.get_specifier()
			container.set_job(
				'paasmaker.job.container',
				{},
				'Register container for %s' % instance_type.name
			)

			self.logger.info("Found %d instance that need to be registered.", to_allocate.count())

			# And for each of those, create the following jobs:
			# - Store port
			#   - Register instance.
			self.instance_list = []
			for instance in to_allocate:
				storeport = container.add_child()
				storeport.set_job(
					'paasmaker.job.coordinate.storeport',
					{
						'instance_id': instance.instance_id,
						'database_id': instance.id
					},
					'Store instance port'
				)

				register = storeport.add_child()
				register.set_job(
					'paasmaker.job.heart.registerinstance',
					instance.flatten_for_heart(),
					'Register instance %s on node %s' % (instance.instance_id, instance.node.name),
					node=instance.node.uuid
				)

			def on_tree_executable():
				self.success({}, "Created all registration jobs.")

			def on_tree_added(root_id):
				self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

			# Add that entire tree into the job manager.
			session.close()
			self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['parent_id'])

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

class RegisterRootJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(RegisterRootJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker', 'heart'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(RegisterRootJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_simple(self):
		runtime_parameters = {
			'launch_command': "python app.py --port=%(port)d"
		}
		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			runtime_parameters,
			'1',
			'tornado-simple'
		)
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		node = self.add_simple_node(session, {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.shell': ['1']
			}
		}, self.configuration)

		# Check that the version is in the correct starting state.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		our_version = session.query(paasmaker.model.ApplicationVersion).get(instance_type.application_version.id)
		self.assertEquals(our_version.state, constants.VERSION.PREPARED)

		RegisterRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop,
			self.stop
		)

		root_job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(root_job_id, self.stop)
		self.wait()

		self.short_wait_hack(length=1)

		#print
		#self.dump_job_tree(root_job_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Make sure the version is in the correct state.
		session.refresh(our_version)
		self.assertEquals(our_version.state, constants.VERSION.READY)

		# Make sure the instances are as expected.
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.REGISTERED
		)

		self.assertEquals(instances.count(), 1, "Should have one registered instance.")

		instance = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.REGISTERED
		).first()

		# Verify the instance was set up.
		self.assertTrue(instance is not None, "Should have one registered instance.")
		self.assertTrue(instance.port in \
			range(self.configuration.get_flat('misc_ports.minimum'), self.configuration.get_flat('misc_ports.maximum')),
			"Port not in expected range.")

		# Deregister the whole lot. This is just to make sure the register task
		# works properly. StartupRootJob will reselect and register instances again.
		DeRegisterRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop,
			self.stop
		)
		deregister_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(deregister_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(deregister_root_id, self.stop)
		self.wait()

		#print
		#self.dump_job_tree(deregister_root_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		session.refresh(instance)

		self.assertEquals(instance.state, constants.INSTANCE.DEREGISTERED, "Instance in wrong state.")

		# Now, hijack this test to test startup of instance. And other stuff.
		StartupRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop,
			self.stop
		)
		# TODO: I have an unbalanced self.stop()/self.wait() pair
		# around here, that causes startup_root_id to sometimes be
		# None. So we loop until we get the real ID. We should fix this...
		startup_root_id = None
		while not startup_root_id:
			startup_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(startup_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(startup_root_id, self.stop)
		self.wait()

		self.short_wait_hack()

		#print
		#self.dump_job_tree(startup_root_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Make sure the version is in the correct state.
		session.refresh(our_version)
		self.assertEquals(our_version.state, constants.VERSION.RUNNING)

		# Make sure the instances are as expected.
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.RUNNING
		)

		self.assertEquals(instances.count(), 1, "Should have one running instance.")

		deregistered_instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.DEREGISTERED
		)

		self.assertEquals(deregistered_instances.count(), 1, "Should have one deregistered instance.")

		other_instance_id = instance.id

		# Fetch the actual instance.
		instance = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.RUNNING
		).first()

		# Verify the instance was set up.
		self.assertNotEquals(other_instance_id, instance.id, "Should be a new instance.")
		self.assertTrue(instance is not None, "Should have one running instance.")
		self.assertTrue(instance.port in \
			range(self.configuration.get_flat('misc_ports.minimum'), self.configuration.get_flat('misc_ports.maximum')),
			"Port not in expected range.")

		# Confirm that the entry exists in the routing table.
		self.configuration.get_router_table_redis(self.stop, self.stop)
		redis = self.wait()

		set_key_version_1 = "instances:%s" % instance.application_instance_type.version_hostname(self.configuration)
		version_instance = instance.get_router_location()

		redis.smembers(set_key_version_1, self.stop)
		routing_table = self.wait()

		self.assertIn(version_instance, routing_table, "Missing entry from routing table.")

		# Refresh the instance object that we have.
		session.refresh(instance)

		self.assertEquals(instance.state, constants.INSTANCE.RUNNING, "Instance not in correct state.")

		# Test the setup_instances() code path here.
		# Shutdown the instance, but instance ID.
		ShutdownRootJob.setup_instances(
			self.configuration,
			[instance],
			self.stop,
			self.stop
		)

		stop_instances_job_id = self.wait()
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(stop_instances_job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(stop_instances_job_id, self.stop)
		self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		# Check it stopped.
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.STOPPED, "Instance not in correct state.")

		# Start it up again, as we can't make it current if it's not running.
		StartupRootJob.setup_instances(
			self.configuration,
			[instance],
			self.stop,
			self.stop
		)

		start_instances_job_id = self.wait()
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(start_instances_job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(start_instances_job_id, self.stop)
		self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		# Check it started.
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.RUNNING, "Instance not in correct state.")

		# Make that version current.
		# TODO: Test when it takes over another version - there is a large set of
		# code paths here not tested.
		CurrentVersionRequestJob.setup_version(
			self.configuration,
			instance_type.application_version.id,
			self.stop,
			self.stop
		)

		current_version_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(current_version_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(current_version_root_id, self.stop)
		self.wait()

		#print
		#print current_version_root_id
		#self.dump_job_tree(current_version_root_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		# Make sure the version is in the correct state.
		session.refresh(our_version)
		self.assertTrue(our_version.is_current, "Version is not current.")
		self.assertEquals(our_version.state, constants.VERSION.RUNNING)

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")
		updated_application_version = session.query(paasmaker.model.ApplicationVersion).get(instance_type.application_version.id)
		self.assertTrue(updated_application_version.is_current, "Version is not current.")

		# Now shut the instance down.
		ShutdownRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop,
			self.stop
		)
		# TODO: I have an unbalanced self.stop()/self.wait() pair
		# around here, that causes shutdown_root_id to sometimes be
		# None. So we loop until we get the real ID. We should fix this...
		shutdown_root_id = None
		while not shutdown_root_id:
			shutdown_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(shutdown_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(shutdown_root_id, self.stop)
		self.wait()

		self.short_wait_hack()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		# Make sure the version is in the correct state.
		session.refresh(our_version)
		self.assertEquals(our_version.state, constants.VERSION.READY)

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Refresh the instance object that we have.
		session.refresh(instance)

		# To check: that the instance is marked as STOPPED.
		instance_data = self.configuration.instances.get_instance(instance.instance_id)
		self.assertEquals(instance_data['instance']['state'], constants.INSTANCE.STOPPED, "Instance not in correct state.")
		self.assertEquals(instance.state, constants.INSTANCE.STOPPED, "Instance not in correct state.")

		# That it's no longer in the routing table.
		redis.smembers(set_key_version_1, self.stop)
		routing_table = self.wait()
		self.assertNotIn(version_instance, routing_table, "Additional entry from routing table.")

		# Fetch the instance path here. Don't do it later because this will recreate it.
		instance_path = self.configuration.get_instance_path(instance.instance_id)

		# Deregister the whole lot.
		DeRegisterRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop,
			self.stop
		)
		deregister_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(deregister_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(deregister_root_id, self.stop)
		self.wait()

		#print
		#self.dump_job_tree(deregister_root_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Make sure the version is in the correct state.
		session.refresh(our_version)
		self.assertEquals(our_version.state, constants.VERSION.PREPARED)

		# To check: the instance directory no longer exists.
		self.assertFalse(os.path.exists(instance_path), "Instance path still exists.")

		# Refresh the instance object that we have.
		session.refresh(instance)

		# To check: that the instance is marked as STOPPED.
		has_instance = self.configuration.instances.has_instance(instance.instance_id)
		self.assertFalse(has_instance, "Instance still exists.")
		self.assertEquals(instance.state, constants.INSTANCE.DEREGISTERED, "Instance not in correct state.")
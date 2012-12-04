
import os
import subprocess
import uuid
import socket

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from startuproot import StartupRootJob
from shutdownroot import ShutdownRootJob
from deregisterroot import DeRegisterRootJob
from instancerootbase import InstanceRootBase

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class RegisterRootJob(BaseJob, InstanceRootBase):
	@staticmethod
	def setup(configuration, application_instance_type, callback, parent=None):
		# Set up the parameters.
		parameters = {}
		parameters['application_instance_type_id'] = application_instance_type.id

		tags = []
		tags.append('workspace:%d' % application_instance_type.application_version.application.workspace.id)
		tags.append('application:%d' % application_instance_type.application_version.application.id)
		tags.append('application_version:%d' % application_instance_type.application_version.id)
		tags.append('application_instance_type:%d' % application_instance_type.id)

		def on_root_job_added(root_job_id):
			def on_select_locations(select_locations_job_id):
				# Done! Callback with the root ID.
				callback(root_job_id)
				# end on_select_locations

			def on_registration_requests(registration_request_job_id):
				# And select the locations for instance.
				configuration.job_manager.add_job(
					'paasmaker.job.coordinate.selectlocations',
					parameters,
					"Select instance locations",
					on_select_locations,
					parent=registration_request_job_id
				)
				# end on_registration_requests

			# And a job to send register requests to nodes.
			configuration.job_manager.add_job(
				'paasmaker.job.coordinate.registerrequest',
				parameters,
				"Registration requests",
				on_registration_requests,
				parent=root_job_id
			)
			# end on_root_job_added

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.registerroot',
			{},
			"Select locations and register instances for %s" % application_instance_type.name,
			on_root_job_added,
			parent=parent,
			tags=tags
		)

	@staticmethod
	def setup_version(configuration, application_version, callback):
		# List all the instance types.
		# Assume we have an open session on the application_version object.
		destroyable_instance_type_list = []
		for instance_type in application_version.instance_types:
			destroyable_instance_type_list.append(instance_type)
		destroyable_instance_type_list.reverse()

		def on_root_job_added(root_job_id):
			# Now go through the list and add sub jobs.
			def add_job(instance_type):
				def job_added(job_id):
					# Try the next one.
					try:
						add_job(destroyable_instance_type_list.pop())
					except IndexError, ex:
						callback(root_job_id)

				RegisterRootJob.setup(
					configuration,
					instance_type,
					job_added,
					parent=root_job_id
				)

			if len(destroyable_instance_type_list) > 0:
				add_job(destroyable_instance_type_list.pop())
			else:
				# This is a bit of a bizzare condition... an
				# application with no instance types.
				callback(root_job_id)

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.registerroot',
			{},
			"Select locations and register instances for %s version %d" % (application_version.application.name, application_version.version),
			on_root_job_added
		)

	def start_job(self, context):
		self.logger.info("Select locations and register instances.")
		self.success({}, "Selected and registered instances.")

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
		node = self.add_simple_node(self.configuration.get_database_session(), {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.shell': ['1']
			}
		}, self.configuration)

		RegisterRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
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
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		session = self.configuration.get_database_session()
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
		self.assertTrue(instance.port in range(42600, 42699), "Port not in expected range.")

		# Now, hijack this test to test startup of instance. And other stuff.
		StartupRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
			self.stop
		)
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

		# Confirm that the entry exists in the routing table.
		self.configuration.get_router_table_redis(self.stop, self.stop)
		redis = self.wait()

		set_key_version_1 = "instances_1.foo.com.%s" % self.configuration.get_flat('pacemaker.cluster_hostname')
		version_instance = "%s:%d" % (socket.gethostbyname(instance.node.route), instance.port)

		redis.smembers(set_key_version_1, self.stop)
		routing_table = self.wait()

		self.assertIn(version_instance, routing_table, "Missing entry from routing table.")

		# Refresh the instance object that we have.
		session.refresh(instance)

		self.assertEquals(instance.state, constants.INSTANCE.RUNNING, "Instance not in correct state.")

		# Now shut the instance down.
		ShutdownRootJob.setup_version(
			self.configuration,
			instance_type.application_version,
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

		# To check: the instance directory no longer exists.
		self.assertFalse(os.path.exists(instance_path), "Instance path still exists.")

		# Refresh the instance object that we have.
		session.refresh(instance)

		# To check: that the instance is marked as STOPPED.
		has_instance = self.configuration.instances.has_instance(instance.instance_id)
		self.assertFalse(has_instance, "Instance still exists.")
		self.assertEquals(instance.state, constants.INSTANCE.DEREGISTERED, "Instance not in correct state.")
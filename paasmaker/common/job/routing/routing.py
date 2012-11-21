
import socket
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE
from ...testhelpers import TestHelpers

import logging

import tornado
from pubsub import pub

import colander

class RoutingUpdateJobParametersSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.Integer())
	add = colander.SchemaNode(colander.Boolean())

class RoutingUpdateJob(BaseJob):
	PARAMETERS_SCHEMA = {MODE.JOB: RoutingUpdateJobParametersSchema()}

	def start_job(self, context):
		self.instance_id = self.parameters['instance_id']

		self.logger.info("Routing table update for instance %s", self.instance_id)
		if self.parameters['add']:
			self.logger.info("Adding instance to routing table.")
		else:
			self.logger.info("Removing instance from the routing table.")

		session = self.configuration.get_database_session()
		self.instance = session.query(
			paasmaker.model.ApplicationInstance
		).get(self.instance_id)

		self.updater = RouterTableUpdate(
			self.configuration,
			self.instance,
			self.parameters['add'],
			self.logger
		)
		self.updater.update(self.on_success, self.on_failure)

	def on_success(self):
		self.logger.info("Successfully updated routing table.")
		self.success({}, "Updated routing table.")

	def on_failure(self, message):
		self.logger.error(message)
		self.failed(message)

class RouterTableUpdate(object):
	def __init__(self, configuration, instance, add, logger):
		self.configuration = configuration
		self.instance = instance
		# Add is True to add, or False to remove.
		self.add = add
		self.logger = logger

		# TODO: Fail if the instance isn't running!

	def update(self, callback, error_callback):
		self.callback = callback
		self.error_callback = error_callback

		# TODO: Replace this with an Async DNS lookup.
		# TODO: IPv6 support!
		self.instance_address = '%s:%d' % (
			socket.gethostbyname(self.instance.node.route),
			self.instance.port
		)

		self.logger.debug("Resolved instance address: %s", self.instance_address)

		# Build a list of sets that this instance should appear in (or not appear in).
		self.instance_sets_yes = []
		self.instance_sets_no = []
		self.instance_log_keys = {}

		log_key = self.instance.application_instance_type.id
		is_current = self.instance.application_instance_type.application_version.is_current

		self.logger.debug("Logging key: %d", log_key)
		self.logger.debug("Is current version: %s", str(is_current))

		# The instance should always have a hostname by it's version and name.
		instance_version_hostname = "%d.%s.%s" % (
			self.instance.application_instance_type.application_version.version,
			self.instance.application_instance_type.application_version.application.name,
			self.configuration.get_flat('pacemaker.cluster_hostname')
		)
		instance_version_hostname = instance_version_hostname.lower()
		self.instance_sets_yes.append(instance_version_hostname)

		self.logger.debug("Version hostname: %s", instance_version_hostname)

		# And the log key to match that is the database instance type ID.
		self.instance_log_keys[instance_version_hostname.lower()] = log_key

		# If the version is current, it will also have a name by it's instance type.
		current_instance_version_hostname = "%s.%s" % (
			self.instance.application_instance_type.application_version.application.name,
			self.configuration.get_flat('pacemaker.cluster_hostname')
		)
		current_instance_version_hostname = current_instance_version_hostname.lower()
		self.logger.debug("Instance version hostname: %s", current_instance_version_hostname)
		if is_current:
			self.instance_sets_yes.append(current_instance_version_hostname)
			self.instance_log_keys[current_instance_version_hostname.lower()] = log_key
		else:
			self.instance_sets_no.append(current_instance_version_hostname)

		# Fetch a list of all the hostnames.
		all_hostnames = []
		self.logger.debug("Instance hostnames:")
		for hostname_orm in self.instance.application_instance_type.hostnames:
			all_hostnames.append("%s" % hostname_orm.hostname.lower())
			self.logger.debug("- %s", hostname_orm)

		# If it's current, they go on the yes list. Otherwise, they go on the
		# no list.
		if is_current:
			self.instance_sets_yes.extend(all_hostnames)
			for hostname in all_hostnames:
				self.instance_log_keys[hostname.lower()] = log_key
		else:
			for hostname in all_hostnames:
				self.instance_sets_no.append(hostname.lower())

		self.logger.debug("Yes hostnames: %s", str(self.instance_sets_yes))
		self.logger.debug("No hostnames: %s", str(self.instance_sets_no))

		# Get the routing table redis.
		self.configuration.get_router_table_redis(self.redis_ready, self.redis_failed)

	def redis_ready(self, redis):
		pipeline = redis.pipeline(True)

		# Now, based on this, we can add/remove entries.
		# If we've been requested to "add" this instance, then we process
		# both the yes and no lists, and also update the log keys.
		# If we've been requested to remove this instance, we process only
		# the "yes" list, but remove instead, and don't update log keys.
		if self.add:
			self.logger.info("Adding to %d sets, and removing from %d.", len(self.instance_sets_yes), len(self.instance_sets_no))
			for key in self.instance_sets_yes:
				pipeline.sadd("instances_" + key, self.instance_address)
			for key in self.instance_sets_no:
				pipeline.srem("instances_" + key, self.instance_address)
			for key, value in self.instance_log_keys.iteritems():
				pipeline.set("logkey_" + key, value)
		else:
			self.logger.info("Removing from %d sets.", len(self.instance_sets_yes))
			for key in self.instance_sets_yes:
				pipeline.srem("instances_" + key, self.instance_address)

		pipeline.execute(callback=self.redis_complete)

	def redis_complete(self, results):
		# Completed the updates.
		self.callback()

	def redis_failed(self, error_message):
		self.error_callback(error_message)

class RoutingTableJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(RoutingTableJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))

	def tearDown(self):
		self.configuration.cleanup()
		super(RoutingTableJobTest, self).tearDown()

	def create_sample_applications(self, session, runtime_name, runtime_parameters, runtime_version):
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		versions = []
		for version in [1, 2]:
			application_version = paasmaker.model.ApplicationVersion()
			application_version.application = application
			application_version.version = version
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
			instance_type.standalone = False
			instance_type.state = constants.INSTANCE_TYPE.PREPARED

			hostname = paasmaker.model.ApplicationInstanceTypeHostname()
			hostname.application_instance_type = instance_type
			hostname.hostname = "test.paasmaker.com"
			instance_type.hostnames.append(hostname)

			session.add(instance_type)
			session.commit()
			session.refresh(instance_type)

			versions.append(instance_type)

		return versions

	def create_instances(self, session, versions, node):
		instances = []
		for version in versions:
			instance = paasmaker.model.ApplicationInstance()
			instance.application_instance_type = version
			instance.node = node
			instance.instance_id = str(uuid.uuid4())
			instance.state = constants.INSTANCE.RUNNING
			instance.port = self.configuration.get_free_port()

			session.add(instance)
			session.commit()

			instances.append(instance)

		return instances

	def in_redis(self, redis, set_name, value):
		#print "Set:", set_name
		redis.smembers(set_name, self.stop)
		result = self.wait()
		#print "Members:", str(result)
		#print "Value:", value

		return value in result

	def not_in_redis(self, redis, set_name, value):
		return not self.in_redis(redis, set_name, value)

	def test_simple(self):
		# Set up the environment.
		s = self.configuration.get_database_session()
		instance_types = self.create_sample_applications(s, 'paasmaker.runtime.php', {}, '5.3')

		node = self.add_simple_node(s, {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.php': ['5.3', '5.3.10']
			}
		}, self.configuration)

		# Map the nodes to the instances.
		instances = self.create_instances(s, instance_types, node)

		# Now, fire them up.
		self.configuration.get_router_table_redis(self.stop, None)
		redis = self.wait()

		# A few variables for later.
		set_key_name = "instances_foo.com.%s" % self.configuration.get_flat('pacemaker.cluster_hostname')
		set_key_version_1 = "instances_1.foo.com.%s" % self.configuration.get_flat('pacemaker.cluster_hostname')
		set_key_version_2 = "instances_2.foo.com.%s" % self.configuration.get_flat('pacemaker.cluster_hostname')
		set_key_hostname = "instances_test.paasmaker.com"
		first_version_instance = "%s:%d" % (socket.gethostbyname(instances[0].node.route), instances[0].port)
		second_version_instance = "%s:%d" % (socket.gethostbyname(instances[1].node.route), instances[1].port)

		# Check that nothing is currently setup.
		redis.smembers(set_key_name, self.stop)
		v = self.wait()
		self.assertEquals(len(v), 0, "Already had something in Redis.")

		# Now insert the first version.
		table_updater = RouterTableUpdate(self.configuration, instances[0], True, logging)
		table_updater.update(self.stop, None)
		self.wait()
		#print

		# Now check to see we have what we expected in Redis.
		# NOTE: No instance will appear in set_key_name yet, because none of them are active.
		self.assertTrue(self.not_in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_1, first_version_instance), "First version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")

		# Add the second instance to the routing table. And make sure they're not
		# overwriting each other.
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_2, second_version_instance), "Second version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, second_version_instance), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, second_version_instance), "Second version in hostname set.")

		# Now make the first version the current version. And check the keys again.
		instances[0].application_instance_type.application_version.make_current(s)
		table_updater = RouterTableUpdate(self.configuration, instances[0], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_1, first_version_instance), "First version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, first_version_instance), "First version version name not found in hostname set.")

		# Now update the second instance again. Nothing should have changed.
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_2, second_version_instance), "Second version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, second_version_instance), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, second_version_instance), "Second version in hostname set.")

		# Now switch the second version to be current. Update the new current instance first.
		# So both instances should exist right now... this is correct, because otherwise
		# we can't switch without downtime.
		instances[1].application_instance_type.application_version.make_current(s)
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.in_redis(redis, set_key_name, first_version_instance), "First version version name not found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, first_version_instance), "First version not in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, second_version_instance), "Second version not in hostname set.")

		# Now update the first instance.
		table_updater = RouterTableUpdate(self.configuration, instances[0], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, second_version_instance), "Second version not in hostname set.")

		# Now that the first instance is out, remove it from the system.
		table_updater = RouterTableUpdate(self.configuration, instances[0], False, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, first_version_instance), "First version version name found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")

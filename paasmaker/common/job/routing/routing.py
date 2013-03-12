
import socket
import uuid
import json

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
	"""
	A job to update routing for a single instance.

	This job reads all data from the instance itself, and acts
	according to the instance state.
	"""
	MODES = {
		MODE.JOB: RoutingUpdateJobParametersSchema()
	}

	def start_job(self, context):
		self.instance_id = self.parameters['instance_id']

		self.logger.info("Routing table update for instance %s", self.instance_id)
		if self.parameters['add']:
			self.logger.info("Adding instance to routing table.")
		else:
			self.logger.info("Removing instance from the routing table.")

		def got_session(session):
			self.session = session
			self.instance = self.session.query(
				paasmaker.model.ApplicationInstance
			).get(self.instance_id)

			if self.instance.application_instance_type.standalone:
				self.session.close()
				self.success({}, "Standalone instance - no routing required.")
			else:
				self.updater = RouterTableUpdate(
					self.configuration,
					self.instance,
					self.parameters['add'],
					self.logger
				)
				self.updater.update(self.on_success, self.on_failure)

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

	def on_success(self):
		self.logger.info("Successfully updated routing table.")
		self.session.close()
		self.success({}, "Updated routing table.")

	def on_failure(self, message):
		self.logger.error(message)
		self.session.close()
		self.failed(message)

	@staticmethod
	def setup_for_instance(configuration, session, instance, add, callback):
		tags = []
		instance_type = instance.application_instance_type
		tags.append('workspace:%d' % instance_type.application_version.application.workspace.id)
		tags.append('application:%d' % instance_type.application_version.application.id)
		tags.append('application_version:%d' % instance_type.application_version.id)
		tags.append('application_instance_type:%d' % instance_type.id)

		update_title = "Update routing for '%s' for application %s, version %d" % (
			instance.instance_id[0:8],
			instance_type.application_version.application.name,
			instance_type.application_version.version
		)

		configuration.job_manager.add_job(
			'paasmaker.job.routing.update',
			{
				'instance_id': instance.id,
				'add': add
			},
			update_title,
			callback=callback,
			tags=tags
		)

class RouterTableUpdate(object):
	def __init__(self, configuration, instance, add, logger):
		self.configuration = configuration
		self.instance = instance
		# Add is True to add, or False to remove.
		self.add = add
		self.logger = logger

		# TODO: Fail if the instance isn't running!
		# TODO: Requires more thinking; instance states are not updated until a little bit
		# later...
		#if self.instance.state == constants.INSTANCE.ALLOCATED:
		#	# This instance won't have a port.
		#	raise ValueError("Supplied instance does not yet have a port - can't insert into routing table.")
		#if self.instance.state != constants.INSTANCE.RUNNING and self.add:
		#	raise ValueError("Supplied instance is not running, and you are trying to add it.")

	def update(self, callback, error_callback):
		self.callback = callback
		self.error_callback = error_callback

		self.instance_address = self.instance.get_router_location()
		self.instance_id = self.instance.instance_id

		self.logger.debug("Resolved instance route: %s", self.instance_address)

		# Build a list of sets that this instance should appear in (or not appear in).
		self.instance_sets_yes = []
		self.instance_sets_no = []
		self.instance_log_keys = {}

		is_current = self.instance.application_instance_type.application_version.is_current

		self.logger.debug("Is current version: %s", str(is_current))

		# The instance should always have a hostname by it's version, workspace, and name.
		instance_version_hostname = self.instance.application_instance_type.version_hostname(self.configuration)
		self.instance_sets_yes.append(instance_version_hostname)

		self.logger.debug("Version hostname: %s", instance_version_hostname)

		# If the version is current, it will also have a name by it's instance type and workspace.
		current_instance_version_hostname = self.instance.application_instance_type.type_hostname(self.configuration)
		self.logger.debug("Instance version hostname: %s", current_instance_version_hostname)
		if is_current:
			self.instance_sets_yes.append(current_instance_version_hostname)
		else:
			self.instance_sets_no.append(current_instance_version_hostname)

		# Fetch a list of all the hostnames.
		all_hostnames = []
		self.logger.debug("Instance hostnames:")
		for hostname_orm in self.instance.application_instance_type.hostnames:
			all_hostnames.append("%s" % hostname_orm.hostname.lower())
			self.logger.debug("- %s", hostname_orm.hostname.lower())

		# If it's current, they go on the yes list. Otherwise, they go on the
		# no list.
		if is_current:
			self.instance_sets_yes.extend(all_hostnames)
		else:
			for hostname in all_hostnames:
				self.instance_sets_no.append(hostname.lower())

		self.logger.debug("Yes hostnames:")
		for hostname in self.instance_sets_yes:
			self.logger.debug("- %s", hostname)
		self.logger.debug("No hostnames:")
		for hostname in self.instance_sets_no:
			self.logger.debug("- %s", hostname)

		# Get the stats redis.
		self.configuration.get_stats_redis(self.stats_redis_ready, self.redis_failed)

	def stats_redis_ready(self, redis):
		# Into this redis, insert the version type ID into the following sets.
		# workspace_<wid>_vtids
		# application_<aid>_vtids
		# version_<vid>_vtids
		# TODO: At this stage, we never remove them.
		pipeline = redis.pipeline(True)
		vtid = self.instance.application_instance_type.id
		wid = self.instance.application_instance_type.application_version.application.workspace.id
		aid = self.instance.application_instance_type.application_version.application.id
		vid = self.instance.application_instance_type.application_version.id
		#nid = self.instance.node.id
		pipeline.sadd('workspace:%d' % wid, vtid)
		pipeline.sadd('application:%d' % aid, vtid)
		pipeline.sadd('version:%d' % vid, vtid)
		#pipeline.sadd('node:%d' % nid, vtid)
		pipeline.execute(self.on_stats_complete)

	def on_stats_complete(self, result):
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
				pipeline.sadd("instances:" + key, self.instance_address)
				pipeline.sadd("instance_ids:" + key, self.instance_id)
			for key in self.instance_sets_no:
				pipeline.srem("instances:" + key, self.instance_address)
				pipeline.srem("instance_ids:" + key, self.instance_id)
		else:
			self.logger.info("Removing from %d sets.", len(self.instance_sets_yes))
			for key in self.instance_sets_yes:
				pipeline.srem("instances:" + key, self.instance_address)
				pipeline.srem("instance_ids:" + key, self.instance_id)

		# Add a serial number to the routing table.
		# We just increment it. It's later used to check that the
		# slaves match the master.
		pipeline.incr("serial")

		def save_redis(result):
			# Ask Redis to save to disk. TODO: tweak the persistence
			# options for Redis to be safer.
			redis.bgsave(callback=self.redis_complete)

		pipeline.execute(callback=save_redis)

	def redis_complete(self, results):
		# Completed the updates.
		self.callback()

	def redis_failed(self, error_message):
		self.error_callback(error_message)

class RouterTablePacemakerUpdate(object):
	def __init__(self, configuration, node, add, logger):
		self.configuration = configuration
		self.node = node
		# Add is True to add, or False to remove.
		self.add = add
		self.logger = logger

	def update(self, callback, error_callback):
		self.callback = callback
		self.error_callback = error_callback

		self.node_address = self.node.get_pacemaker_location()

		self.logger.debug("Resolved pacemaker address: %s", self.node_address)

		self.hostname = "%s.%s" % (
			self.configuration.get_flat('pacemaker.pacemaker_prefix'),
			self.configuration.get_flat('pacemaker.cluster_hostname')
		)

		# Get the routing table redis.
		self.configuration.get_router_table_redis(self.redis_ready, self.redis_failed)

	def redis_ready(self, redis):
		pipeline = redis.pipeline(True)

		if self.add:
			self.logger.info("Adding pacemaker to %s.", self.hostname)
			pipeline.sadd("instances:" + self.hostname, self.node_address)
			pipeline.sadd("instance_ids:" + self.hostname, self.node.uuid)
		else:
			self.logger.info("Removing pacemaker from %s.", self.hostname)
			pipeline.srem("instances:" + self.hostname, self.node_address)
			pipeline.srem("instance_ids:" + self.hostname, self.node.uuid)

		# Add a serial number to the routing table.
		# We just increment it. It's later used to check that the
		# slaves match the master.
		pipeline.incr("serial")

		def save_redis(result):
			# Ask Redis to save to disk. TODO: tweak the persistence
			# options for Redis to be safer.
			redis.bgsave(callback=self.redis_complete)

		pipeline.execute(callback=save_redis)

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
		workspace.stub = 'test'

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
		self.configuration.get_database_session(self.stop, None)
		s = self.wait()
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
		set_key_name = "instances:%s" % instances[0].application_instance_type.type_hostname(self.configuration)
		set_key_name_id = "instance_ids:%s" % instances[0].application_instance_type.type_hostname(self.configuration)
		set_key_version_1 = "instances:%s" % instances[0].application_instance_type.version_hostname(self.configuration)
		set_key_version_1_id = "instance_ids:%s" % instances[0].application_instance_type.version_hostname(self.configuration)
		set_key_version_2 = "instances:%s" % instances[1].application_instance_type.version_hostname(self.configuration)
		set_key_version_2_id = "instance_ids:%s" % instances[1].application_instance_type.version_hostname(self.configuration)
		set_key_hostname = "instances:test.paasmaker.com"
		set_key_hostname_id = "instance_ids:test.paasmaker.com"
		first_version_instance = instances[0].get_router_location()
		first_version_instance_id = instances[0].instance_id
		second_version_instance = instances[1].get_router_location()
		second_version_instance_id = instances[1].instance_id

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
		self.assertTrue(self.not_in_redis(redis, set_key_name_id, first_version_instance_id), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_1, first_version_instance), "First version version name not found.")
		self.assertTrue(self.in_redis(redis, set_key_version_1_id, first_version_instance_id), "First version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2_id, first_version_instance_id), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname_id, first_version_instance_id), "First version in hostname set.")

		# Add the second instance to the routing table. And make sure they're not
		# overwriting each other.
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_name_id, second_version_instance_id), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_2, second_version_instance), "Second version version name not found.")
		self.assertTrue(self.in_redis(redis, set_key_version_2_id, second_version_instance_id), "Second version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, second_version_instance), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1_id, second_version_instance_id), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, second_version_instance), "Second version in hostname set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname_id, second_version_instance_id), "Second version in hostname set.")

		# Now make the first version the current version. And check the keys again.
		instances[0].application_instance_type.application_version.make_current(s)
		table_updater = RouterTableUpdate(self.configuration, instances[0], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name_id, first_version_instance_id), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_1, first_version_instance), "First version version name not found.")
		self.assertTrue(self.in_redis(redis, set_key_version_1_id, first_version_instance_id), "First version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2_id, first_version_instance_id), "First version version name found in second.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, first_version_instance), "First version version name not found in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname_id, first_version_instance_id), "First version version name not found in hostname set.")

		# Now update the second instance again. Nothing should have changed.
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_name_id, second_version_instance_id), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_version_2, second_version_instance), "Second version version name not found.")
		self.assertTrue(self.in_redis(redis, set_key_version_2_id, second_version_instance_id), "Second version version name not found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, second_version_instance), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1_id, second_version_instance_id), "Second version version name found in first.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, second_version_instance), "Second version in hostname set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname_id, second_version_instance_id), "Second version in hostname set.")

		# Now switch the second version to be current. Update the new current instance first.
		# So both instances should exist right now... this is correct, because otherwise
		# we can't switch without downtime.
		instances[1].application_instance_type.application_version.make_current(s)
		table_updater = RouterTableUpdate(self.configuration, instances[1], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.in_redis(redis, set_key_name, first_version_instance), "First version version name not found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name_id, first_version_instance_id), "First version version name not found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name_id, second_version_instance_id), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, first_version_instance), "First version not in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname_id, first_version_instance_id), "First version not in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, second_version_instance), "Second version not in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname_id, second_version_instance_id), "Second version not in hostname set.")

		# Now update the first instance.
		table_updater = RouterTableUpdate(self.configuration, instances[0], True, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_name_id, first_version_instance_id), "First version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name, second_version_instance), "Second version version name found in app name set.")
		self.assertTrue(self.in_redis(redis, set_key_name_id, second_version_instance_id), "Second version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname_id, first_version_instance_id), "First version in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname, second_version_instance), "Second version not in hostname set.")
		self.assertTrue(self.in_redis(redis, set_key_hostname_id, second_version_instance_id), "Second version not in hostname set.")

		# Now that the first instance is out, remove it from the system.
		table_updater = RouterTableUpdate(self.configuration, instances[0], False, logging)
		table_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, set_key_name, first_version_instance), "First version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_name_id, first_version_instance_id), "First version version name found in app name set.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1, first_version_instance), "First version version name found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_1_id, first_version_instance_id), "First version version name found.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2, first_version_instance), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_version_2_id, first_version_instance_id), "First version version name found in second.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname, first_version_instance), "First version in hostname set.")
		self.assertTrue(self.not_in_redis(redis, set_key_hostname_id, first_version_instance_id), "First version in hostname set.")

		def got_table(table, serial, session):
			got_table.table = table
			got_table.serial = serial
			session.close()
			self.stop()

		# Dump out the table.
		dumper = paasmaker.router.tabledump.RouterTableDump(self.configuration, got_table, self.stop)
		dumper.dump()
		self.wait()

		dump = got_table.table
		serial = got_table.serial

		self.assertEquals(len(dump), 3, "Should have had three entries in the routing table.")
		#print json.dumps(dump, indent=4, sort_keys=True, cls=paasmaker.util.JsonEncoder)
		self.assertTrue(serial > 0, "Serial number was not incremented.")

		pacemaker_route = node.get_pacemaker_location()
		pacemaker_hostname = "%s.%s" % (
			self.configuration.get_flat('pacemaker.pacemaker_prefix'),
			self.configuration.get_flat('pacemaker.cluster_hostname')
		)
		pacemaker_set = "instances:%s" % pacemaker_hostname

		self.assertTrue(self.not_in_redis(redis, pacemaker_set, pacemaker_route), "Pacemaker is listed in routing table.")

		pacemaker_updater = RouterTablePacemakerUpdate(self.configuration, node, True, logging)
		pacemaker_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.in_redis(redis, pacemaker_set, pacemaker_route), "Pacemaker not listed in routing table.")

		pacemaker_updater = RouterTablePacemakerUpdate(self.configuration, node, False, logging)
		pacemaker_updater.update(self.stop, None)
		self.wait()

		self.assertTrue(self.not_in_redis(redis, pacemaker_set, pacemaker_route), "Pacemaker listed in routing table.")
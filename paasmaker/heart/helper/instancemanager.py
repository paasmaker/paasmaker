#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import logging
import json
import unittest
import uuid

import paasmaker
from paasmaker.common.core import constants

import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class InstanceManager(object):
	"""
	A class to manage instance data, for each heart node.

	Instance data is written out to a flat JSON encoded file on each node.
	This is so each heart doesn't require a database or other special storage
	system.
	"""
	def __init__(self, configuration):
		self.configuration = configuration
		# Mapping of instance id -> data.
		self.catalog = {}

		# Reload our catalog from disk, if it exists.
		self.load()

	def _get_catalog_path(self):
		return os.path.join(self.configuration.get_flat('scratch_directory'), 'heart_catalog.json')

	def load(self):
		"""
		Load the heart catalog from disk. Starts with an empty
		catalog if this is the first time this node has been active.
		"""
		# Load the catalog from the disk.
		path = self._get_catalog_path()
		logger.debug("Heart catalog path: %s", path)
		if os.path.exists(path):
			logger.debug("Using existing catalog, as it exists.")
			fp = open(path, 'r')
			contents = fp.read()
			fp.close()

			try:
				self.catalog = json.loads(contents)
				logger.info("Loaded heart catalog.")
				logger.debug("Catalog: %s", str(self.catalog))
			except ValueError, ex:
				# Couldn't decode. Start with a blank one,
				# and the pacemaker should update us soon.
				logger.error("Heart catalog is broken, so using a blank catalog.")
				self.catalog = {}

	def save(self, report_to_master=True):
		"""
		Save the heart catalog to disk. This should be called
		after any change to the instance data. If the report_to_master
		flag is set, it triggers an update report to the master.

		:arg bool report_to_master: If true, triggers an update
			of instance status to the master.
		"""
		# Save the catalog to disk, writing a new one out and then
		# renaming it, to make it atomic.
		path = self._get_catalog_path()
		path_temp = path + ".temp"
		fp = open(path_temp, 'w')
		fp.write(json.dumps(self.catalog, cls=paasmaker.util.jsonencoder.JsonEncoder))
		fp.close()
		os.rename(path_temp, path)
		logger.debug("Wrote out new catalog.")
		# Trigger a writeback to the master node.
		if report_to_master:
			self.configuration.instance_status_trigger()

	def add_instance(self, instance_id, data):
		"""
		Add an instance to this catalog.

		Raise an exception if the instance already exists.

		The catalog is automatically saved.

		:arg str instance_id: The instance ID to add.
		:arg dict data: The instance data.
		"""
		if self.catalog.has_key(instance_id):
			raise KeyError("We already have an instance for instance id %s" % instance_id)

		# Add it and save immediately.
		logger.info("Adding instance %s to our collection.", instance_id)
		# Create a dict for data for the runtime - the runtime can
		# store what it likes in there.
		if not data.has_key('runtime'):
			data['runtime'] = {'exit': {'keys': []}}
		self.catalog[instance_id] = data
		self.save()

	def remove_instance(self, instance_id):
		"""
		Remove the instance from our catalog.

		The catalog is automatically saved.

		:arg str instance_id: The instance ID to remove.
		"""
		if not self.catalog.has_key(instance_id):
			raise KeyError("We do not have an instance for %s" % instance_id)

		del self.catalog[instance_id]
		self.save()

	def get_state(self, instance_id):
		"""
		Get the last known state of the given instance ID.

		Does not actively check the instance's state.

		:arg str instance_id: The instance ID to return the
			state of.
		"""
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		return self.catalog[instance_id]['instance']['state']

	def change_state(self, instance_id, state):
		"""
		Change the given instance ID's state. The catalog
		is saved automatically.

		:arg str instance_id: The instance ID to change.
		:arg str state: The state to change to.
		"""
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		logger.debug("Recording instance %s change %s -> %s", instance_id, self.catalog[instance_id]['instance']['state'], state)
		self.catalog[instance_id]['instance']['state'] = state
		self.save()

	def get_instance(self, instance_id):
		"""
		Get all instance data for the given instance ID.

		:arg str instance_id: The instance ID to fetch data for.
		"""
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		return self.catalog[instance_id]

	def has_instance(self, instance_id):
		"""
		Determine if our catalog has an instance.

		:arg str instance_id: The instance ID to check.
		"""
		return self.catalog.has_key(instance_id)

	def get_instance_list(self):
		"""
		Return a list of instance IDs and their states.
		The result is a dict like so::

			{
				'<instance id 1>': 'STATE',
				...
			}
		"""
		result = {}
		for instance_id, data in self.catalog.iteritems():
			result[instance_id] = data['instance']['state']

		return result

	def generate_exit_key(self, instance_id):
		"""
		Generate an exit token for the given instance ID, storing the token
		along with the instance's data, and saving the catalog.

		This does not replace an existing exit key; it generates a new one
		and adds it to the list of valid exit keys.

		:arg str instance_id: The instance ID to generate the key for.
		"""
		instance = self.get_instance(instance_id)
		exit_key = str(uuid.uuid4())
		instance['runtime']['exit']['keys'].append(exit_key)
		self.save()
		return exit_key

	def get_used_ports(self):
		"""
		Get a list of ports already assigned to instances from the catalog.

		This is designed to pre-seed the port allocator upon startup,
		to speed up locating free ports.

		The return value is a list of ports.
		"""
		ports = []
		for instance_id, data in self.catalog.iteritems():
			if data.has_key('instance') and data['instance'].has_key('port'):
				ports.append(data['instance']['port'])

		return ports

	def check_instances_runtime(self, runtime_logger, callback):
		"""
		Check all instances in the catalog, during runtime.

		This is designed to be run periodically on each heart node.
		It goes over all instances in the catalog, checking their state
		matches what is stored. Once complete, it will call the supplied
		callback. The callback is supplied a list of instance IDs that
		have changed state as a result of the checks.

		:arg Logger runtime_logger: The logger to send messages about the progress
			of the checks to.
		:arg callable callback: The callback to call when complete.
		"""
		instances = self.catalog.keys()
		altered_instances = []
		runtime_logger.info("Checking %d instances registered on this node.", len(instances))

		def done_instances():
			if len(altered_instances) > 0:
				# Trigger a save, which also reports the updates back to the master.
				self.save()
			runtime_logger.info("Completed checking instances. %d altered instances.", len(altered_instances))
			callback(altered_instances)

		def check_instance(instance_id, processor):
			def on_success_instance(message):
				# All good. No action to take.
				runtime_logger.info("Instance %s is still running.", instance_id)
				processor.next()
				# end of on_success_instance()

			def on_error_instance(message, exception=None):
				# Instance is no longer running.
				# Place it into the ERROR state, and then we'll let
				# the pacemaker know shortly. It can then organise to
				# start a new one for us.
				runtime_logger.error("Instance %s is no longer running!", instance_id)
				runtime_logger.error(message)

				# Record the error against the instance.
				instance_logger = self.configuration.get_job_logger(instance_id)
				instance_logger.error("Determined not to be running. Pacemaker will decide the fate now.")
				instance_logger.error(message)
				if exception:
					instance_logger.error("Exception:", exc_info=exception)
				instance_logger.finished()

				data = self.get_instance(instance_id)
				data['instance']['state'] = constants.INSTANCE.ERROR
				# Save the data, but delay reporting back until the checks are complete.
				self.save(False)
				altered_instances.append(instance_id)
				processor.next()
				# end of on_error_instance()

			data = self.get_instance(instance_id)
			runtime_logger.info("Instance %s recorded as being in state %s", instance_id, data['instance']['state'])

			# If it's supposed to be running, load the plugin and check that
			# it's actually running.
			if data['instance']['state'] == constants.INSTANCE.RUNNING:
				# Load the plugin, and check that it's actually running.
				plugin_exists = self.configuration.plugins.exists(
					data['instance_type']['runtime_name'],
					paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
				)

				if not plugin_exists:
					# Well, that's an error.
					data['instance']['state'] = constants.INSTANCE.ERROR
					self.save()
					altered_instances.append(instance_id)
					runtime_logger.error("Instance %s has a non existent runtime %s.", instance_id, data['instance_type']['runtime_name'])

					instance_logger = self.configuration.get_job_logger(instance_id)
					instance_logger.error("This heart node no longer has runtime %s.", data['instance_type']['runtime_name'])
					instance_logger.finished()

					processor.next()
				else:
					instance_logger = self.configuration.get_job_logger(instance_id)
					runtime = self.configuration.plugins.instantiate(
						data['instance_type']['runtime_name'],
						paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
						data['instance_type']['runtime_parameters'],
						instance_logger
					)

					runtime.status(
						instance_id,
						on_success_instance,
						on_error_instance
					)
			else:
				# Not running - just check the next instance.
				processor.next()

			# end of check_instance()

		processor = paasmaker.util.callbackprocesslist.CallbackProcessList(
			instances,
			check_instance,
			done_instances
		)
		processor.start()

	def check_instances_startup(self, callback):
		"""
		Check all instances in the catalog.

		This is designed to be run on startup. It goes over all instances
		in the catalog, checking their state matches what is stored. Once
		complete, it will call the supplied callback. The callback is supplied
		a list of instance IDs that have changed state as a result of the
		checks.

		:arg callable callback: The callback to call when complete.
		"""
		# TODO: Add unit tests for this. Desperately required.
		# TODO: Refactor this code. It's way too complicated and has far
		# too many code paths for a single method.
		instances = self.catalog.keys()
		altered_instances = []
		logger.info("Checking %d instances on startup.", len(instances))

		# Fetch the flag that indicates if we're supposed to shut down
		# applications on exit. This alters how we handle SUSPENDED instances
		# in development mode.
		always_shutdown = self.configuration.get_flat('heart.shutdown_on_exit')

		def next_instance():
			if len(instances) > 0:
				check_instance(instances.pop())
			else:
				callback(altered_instances)

		def check_instance(instance_id):
			def on_success_instance(message):
				# All good. No action to take.
				logger.info("Instance %s is still running.", instance_id)
				data = self.get_instance(instance_id)
				data['instance']['state'] = constants.INSTANCE.RUNNING
				self.save()
				next_instance()
				# end of on_success_instance()

			def on_error_instance(message, exception=None):
				def real_on_error_instance(message, exception=None):
					# Normal production handling.
					# It's no longer running. Mark it as SUSPENDED.
					logger.error("Instance %s is no longer running!", instance_id)
					logger.error(message)

					# Record the error against the instance.
					instance_logger = self.configuration.get_job_logger(instance_id)
					instance_logger.error("Determined not to be running. Pacemaker will decide the fate now.")
					instance_logger.error(message)
					if exception:
						instance_logger.error("Exception:", exc_info=exception)
					instance_logger.finished()

					data = self.get_instance(instance_id)
					data['instance']['state'] = constants.INSTANCE.SUSPENDED
					self.save()
					altered_instances.append(instance_id)
					next_instance()
					# end of real_on_error_instance()

				if always_shutdown:
					# Development mode handling. The instance
					# was placed into suspended state, and sure enough,
					# it's no longer running. So try to start it up.
					instance_logger = self.configuration.get_job_logger(instance_id)
					data = self.get_instance(instance_id)
					runtime = self.configuration.plugins.instantiate(
						data['instance_type']['runtime_name'],
						paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
						data['instance_type']['runtime_parameters'],
						instance_logger
					)

					runtime.start(
						instance_id,
						on_success_instance,
						real_on_error_instance
					)
				else:
					# Do the production handling.
					real_on_error_instance(message, exception)

				# end of on_error_instance()

			data = self.get_instance(instance_id)
			logger.info("Instance %s in state %s", instance_id, data['instance']['state'])
			# The state of the instance will be RUNNING if the Heart crashed.
			# The state of the instance will be SUSPENDED if the Heart shutdown and
			# left the apps running. In these cases, check to see if it's still running.
			# If it's not, it's state remains as SUSPENDED and the Pacemaker will decide
			# what to do with it.
			if data['instance']['state'] == constants.INSTANCE.RUNNING or \
				data['instance']['state'] == constants.INSTANCE.SUSPENDED:
				# If it's marked as running, it's supposed to be running - check that it is.
				# If it's marked as suspended, it might still be running, so check that state.
				# TODO: This suddenly ties the instance manager to the
				# plugins system. This is probably ok, but consider this further.
				plugin_exists = self.configuration.plugins.exists(
					data['instance_type']['runtime_name'],
					paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
				)

				if not plugin_exists:
					# Well, that's an error.
					data['instance']['state'] = constants.INSTANCE.ERROR
					self.save()
					altered_instances.append(instance_id)
					logger.error("Instance %s has a non existent runtime %s.", instance_id, data['instance_type']['runtime_name'])

					instance_logger = self.configuration.get_job_logger(instance_id)
					instance_logger.error("This heart node no longer has runtime %s.", data['instance_type']['runtime_name'])
					instance_logger.finished()

					next_instance()
				else:
					instance_logger = self.configuration.get_job_logger(instance_id)
					runtime = self.configuration.plugins.instantiate(
						data['instance_type']['runtime_name'],
						paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
						data['instance_type']['runtime_parameters'],
						instance_logger
					)

					runtime.status(
						instance_id,
						on_success_instance,
						on_error_instance
					)
			else:
				next_instance()
			# end of check_instance()

		next_instance()

	def check_instances_shutdown(self, callback):
		"""
		Check all registered instances on shutdown. May change
		the state of instances as required.

		Calls the supplied callback once done, with a list of instance
		IDs that were altered.

		:arg callable callback: The callback to call when complete.
		"""
		# TODO: Add unit tests for this. Desperately required.
		# TODO: Refactor this code. It's way too complicated and has far
		# too many code paths for a single method.
		instances = self.catalog.keys()
		altered_instances = []
		logger.info("Checking %d instances on shutdown.", len(instances))

		# What are we doing here? Basically, if it's running,
		# mark it as SUSPENDED. We don't kill the instance, unless it
		# is an exclusive instance. When the state change gets reported
		# back to the master, it will be taken out of the routing table.
		# On startup, we check all the instances, and if they're still
		# running, they get their state updated. If they're not running
		# the pacemaker can make a decision based on it's recorded state.

		def next_instance():
			if len(instances) > 0:
				check_instance(instances.pop())
			else:
				callback(altered_instances)

		def check_instance(instance_id):
			data = self.get_instance(instance_id)
			logger.info("Checking instance %s currently in state %s", instance_id, data['instance']['state'])
			if data['instance']['state'] == constants.INSTANCE.RUNNING:
				always_shutdown = self.configuration.get_flat('heart.shutdown_on_exit')

				# TODO: Document the caution below somewhere appropriate.
				# CAUTION: the heart.shutdown_on_exit setting is NOT FOR PRODUCTION.
				# The instance will likely be terminated BEFORE the routing table is
				# updated resulting in dropped traffic. It's designed to allow nodes
				# to clean up after themselves in the case of tests, development,
				# or trials.

				if always_shutdown or data['instance_type']['exclusive']:
					logger.info("Instance %s is exclusive, or we're configured to shutdown, so really stopping.", instance_id)
					# Needs to be stopped.
					plugin_exists = self.configuration.plugins.exists(
						data['instance_type']['runtime_name'],
						paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
					)

					if not plugin_exists:
						# Well, that's an error.
						data['instance']['state'] = constants.INSTANCE.ERROR
						self.save()
						altered_instances.append(instance_id)
						logger.error("Instance %s has a non existent runtime %s.", instance_id, data['instance_type']['runtime_name'])

						instance_logger = self.configuration.get_job_logger(instance_id)
						instance_logger.error("This heart node doesn't have runtime %s.", data['instance_type']['runtime_name'])
						instance_logger.finished()

						next_instance()
					else:
						def on_success_shutdown(message):
							# All good. It's shut down now.
							logger.info("Instance %s is now shutdown.", instance_id)
							data = self.get_instance(instance_id)
							if data['instance_type']['exclusive']:
								# It's stopped. The Pacemaker will pick this up and take
								# corrective actions based on this.
								data['instance']['state'] = constants.INSTANCE.STOPPED
							else:
								# It's suspended. The pacemaker will ask us to start
								# it back up later if needed.
								data['instance']['state'] = constants.INSTANCE.SUSPENDED
							self.save(report_to_master=False)
							next_instance()
							# end of on_success_instance()

						def on_error_shutdown(message, exception=None):
							# Something went wrong... put it into error state.
							logger.error("Instance %s is now in error.", instance_id)
							logger.error(message)

							# Record the error against the instance.
							instance_logger = self.configuration.get_job_logger(instance_id)
							instance_logger.error("Instance %s is in error.")
							instance_logger.error(message)
							if exception:
								instance_logger.error("Exception:", exc_info=exception)

							data = self.get_instance(instance_id)
							data['instance']['state'] = constants.INSTANCE.ERROR
							self.save(report_to_master=False)
							altered_instances.append(instance_id)
							next_instance()
							# end of on_error_instance()

						instance_logger = self.configuration.get_job_logger(instance_id)
						runtime = self.configuration.plugins.instantiate(
							data['instance_type']['runtime_name'],
							paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
							data['instance_type']['runtime_parameters'],
							instance_logger
						)

						runtime.stop(
							instance_id,
							on_success_shutdown,
							on_error_shutdown
						)
				else:
					# Mark it as suspended and move on.
					logger.info("Marking instance %s as SUSPENDED.", instance_id)
					data['instance']['state'] = constants.INSTANCE.SUSPENDED
					self.save(report_to_master=False)
					next_instance()
			else:
				next_instance()
			# end of check_instance()

		next_instance()

class InstanceManagerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(InstanceManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['heart'])

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(InstanceManagerTest, self).tearDown()

	def test_simple(self):
		manager = InstanceManager(self.configuration)

		# Check that it's empty.
		self.assertEquals(len(manager.get_instance_list().keys()), 0, "Already has instances?")

		# Check that the catalog file doesn't exist yet.
		path = manager._get_catalog_path()
		self.assertFalse(os.path.exists(path), "Catalog already exists...")

		# Make sure it throws an exception if we try to fetch an invalid ID.
		try:
			manager.get_instance('invalid')
			self.assertTrue(False, "Should have thrown exception.")
		except KeyError, ex:
			self.assertTrue(True, "Threw exception correctly.")
		try:
			manager.get_state('invalid')
			self.assertTrue(False, "Should have thrown exception.")
		except KeyError, ex:
			self.assertTrue(True, "Threw exception correctly.")

		# Add an instance.
		instance = {'instance': {'state': constants.INSTANCE.ALLOCATED}}
		manager.add_instance('foo', instance)

		# The catalog file should now exist.
		self.assertTrue(os.path.exists(path), "Catalog file doesn't exist.")

		# Try to add it again - should throw exception.
		try:
			manager.add_instance('foo', instance)
			self.assertTrue(False, "Should have thrown exception.")
		except KeyError, ex:
			self.assertTrue(True, "Threw exception correctly.")

		# Get the state for that instance.
		self.assertEquals(manager.get_state('foo'), constants.INSTANCE.ALLOCATED, "Instance state is not as expected.")

		# And check that it exists in the list.
		instance_list = manager.get_instance_list()
		self.assertTrue(instance_list.has_key('foo'), "Missing in output list.")
		self.assertEquals(instance_list['foo'], constants.INSTANCE.ALLOCATED, "Incorrect state.")

		# Check that we can modify the returned entry.
		entry = manager.get_instance('foo')
		entry['bar'] = 'baz'

		reference = manager.get_instance('foo')

		self.assertTrue(reference.has_key('bar'), "Value did not copy over.")
		self.assertEquals(reference['bar'], entry['bar'], "Value did not match.")

		manager.save()
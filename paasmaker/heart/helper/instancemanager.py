
import os
import logging
import json
import unittest

import paasmaker
from paasmaker.common.core import constants

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class InstanceManager(object):
	def __init__(self, configuration):
		self.configuration = configuration
		# Mapping of instance id -> data.
		self.catalog = {}

		# Reload our catalog from disk, if it exists.
		self.load()

	def get_catalog_path(self):
		return os.path.join(self.configuration.get_flat('scratch_directory'), 'heart_catalog.json')

	def load(self):
		# Load the catalog from the disk.
		path = self.get_catalog_path()
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

	def save(self):
		# Save the catalog to disk, writing a new one out and then
		# renaming it, to make it atomic.
		path = self.get_catalog_path()
		path_temp = path + ".temp"
		fp = open(path_temp, 'w')
		fp.write(json.dumps(self.catalog))
		fp.close()
		os.rename(path_temp, path)
		logger.debug("Wrote out new catalog.")

	def add_instance(self, instance_id, data):
		if self.catalog.has_key(instance_id):
			raise KeyError("We already have an instance for instance id %s" % instance_id)

		# Add it and save immediately.
		logger.info("Adding instance %s to our collection.", instance_id)
		# Create a dict for data for the runtime - the runtime can
		# store what it likes in there.
		data['runtime'] = {}
		self.catalog[instance_id] = data
		self.save()

	def get_state(self, instance_id):
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		return self.catalog[instance_id]['instance']['state']

	def change_state(self, instance_id, state):
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		logger.debug("Recording instance %s change %s -> %s", instance_id, self.catalog[instance_id]['instance']['state'], state)
		self.catalog[instance_id]['instance']['state'] = state
		self.save()

	def get_instance(self, instance_id):
		if not self.catalog.has_key(instance_id):
			raise KeyError("Unknown instance %s" % instance_id)

		return self.catalog[instance_id]

	def has_instance(self, instance_id):
		return self.catalog.has_key(instance_id)

	def get_instance_list(self):
		result = {}
		for instance_id, data in self.catalog.iteritems():
			result[instance_id] = data['instance']['state']

		return result

	def get_used_ports(self):
		ports = []
		for instance_id, data in self.catalog.iteritems():
			if data['instance'].has_key('port'):
				ports.append(data['instance']['port'])

		return ports

class InstanceManagerTest(unittest.TestCase):
	def setUp(self):
		super(InstanceManagerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['heart'])

	def tearDown(self):
		self.configuration.cleanup()
		super(InstanceManagerTest, self).tearDown()

	def test_simple(self):
		manager = InstanceManager(self.configuration)

		# Check that it's empty.
		self.assertEquals(len(manager.get_instance_list().keys()), 0, "Already has instances?")

		# Check that the catalog file doesn't exist yet.
		path = manager.get_catalog_path()
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
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import random

import colander
from base import BasePlacement, BasePlacementTest
from paasmaker.common.core import constants
import paasmaker

class DefaultPlacementConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class DefaultPlacementParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

# Default placement algorithm.
class DefaultPlacement(BasePlacement):
	"""
	This is the default placement algorithm, that takes into account
	the number of applications on each node, the node tags, and tries
	not to start more than one instance of an application on a single node,
	but will allow repeats to satisfy quotas.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.PLACEMENT: DefaultPlacementParametersSchema()
	}
	OPTIONS_SCHEMA = DefaultPlacementConfigurationSchema()
	API_VERSION = "0.9.0"

	def _fail_if_none(self, nodes, callback, reason):
		if len(nodes) == 0:
			callback(reason)
			return True
		else:
			return False

	def choose(self, session, instance_type, quantity, callback, error_callback):
		# Query active nodes first.
		nodes = self._get_active_nodes(session)

		self.logger.info("Stage 1: Found %d active nodes.", len(nodes))

		if self._fail_if_none(nodes, error_callback, "No active nodes found to run this instance."):
			return

		physical_nodes = len(nodes)

		# Filter by the required runtime.
		runtime_tags = {}
		runtime_tags[instance_type.runtime_name] = [instance_type.runtime_version]
		self.logger.info("Stage 2: Filtering to these runtimes: %s", str(runtime_tags))
		nodes = self._filter_by_tags(nodes, {'runtimes': runtime_tags})
		self.logger.info("Stage 2: Found %d nodes that can run this instance.", len(nodes))

		if self._fail_if_none(nodes, error_callback, "No nodes can service the runtime %s, version %s." % (instance_type.runtime_name, instance_type.runtime_version)):
			return

		runtime_nodes = len(nodes)

		# Filter them by the user tags supplied.
		tags = {}
		if self.parameters.has_key('tags'):
			tags = self.parameters['tags']
		self.logger.info("Stage 3: Filtering to nodes with these tags: %s", str(tags))
		nodes = self._filter_by_tags(nodes, {'node': tags})
		self.logger.info("Stage 3: Found %d nodes that match these tags.", len(nodes))

		if self._fail_if_none(nodes, error_callback, "No nodes match the supplied tags: %s" % str(tags)):
			return

		tagged_nodes = len(nodes)

		if len(nodes) < quantity:
			self.logger.warning("Not enough nodes for one instance per node.")
			# We need duplicates to make this work.
			# Use them in order and loop around.
			multiples = (quantity / len(nodes)) + 1
			nodes = nodes * multiples
			nodes = nodes[0:quantity]
		else:
			# Now choose quantity number of nodes.
			# They're in order of score, so just grab the first few.
			nodes = nodes[0:quantity]

		self.logger.info("Stage 4: Successfully selected %d nodes." % len(nodes))

		callback(nodes,
			"Successfully chosen %d nodes, from %d physical nodes, and %d nodes that can run this instance." % \
			(len(nodes), physical_nodes, runtime_nodes)
		)

class DefaultPlacementTest(BasePlacementTest):

	def test_core_tags_filter(self):
		self.registry.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)
		plugin = self.registry.instantiate(
			'paasmaker.placement.default',
			paasmaker.util.plugin.MODE.PLACEMENT,
			{}
		)

		# Test node.
		ctr = 1
		n = paasmaker.model.Node(name='tags-test%d' % ctr,
				route='%d.tags-test.paasmaker.com' % ctr,
				apiport=888,
				uuid='%s-tags-uuid' % ctr,
				state=constants.NODE.ACTIVE)
		n.heart = True
		n.tags = {
			'runtimes': {
				'paasmaker.runtime.php': ['5.3', '5.3.10']
			},
			'node': {
				'one': 'two'
			}
		}
		nodes = [n]

		# This should return all the nodes, because no qualifying tags are supplied.
		result = plugin._filter_by_tags(nodes, {})
		self.assertEquals(len(result), 1, "Should have returned the node.")

		# This should return no nodes, because there are tags that must meet.
		result = plugin._filter_by_tags(nodes, {'foo': 'bar'})
		self.assertEquals(len(result), 0, "Should have returned no nodes.")

		# This should return the node, because the value matches.
		result = plugin._filter_by_tags(nodes, {'node': {'one': 'two'}})
		self.assertEquals(len(result), 1, "Should have returned the node.")

		# This should not return the node, because the value does not matches.
		result = plugin._filter_by_tags(nodes, {'node': {'one': 'one'}})
		self.assertEquals(len(result), 0, "Should have returned no nodes.")

		# Try to fetch a runtime - one that doesn't exist.
		result = plugin._filter_by_tags(nodes, {'runtimes': {'paasmaker.runtime.noexist': ['1.0']}})
		self.assertEquals(len(result), 0, "Should have returned no nodes.")

		# Try to fetch a runtime that matches.
		result = plugin._filter_by_tags(nodes, {'runtimes': {'paasmaker.runtime.php': ['5.3.10']}})
		self.assertEquals(len(result), 1, "Should have returned the node.")
		result = plugin._filter_by_tags(nodes, {'runtimes': {'paasmaker.runtime.php': ['5.3']}})
		self.assertEquals(len(result), 1, "Should have returned the node.")

		# Try to fetch a runtime that doesn't match in version.
		result = plugin._filter_by_tags(nodes, {'runtimes': {'paasmaker.runtime.php': ['5']}})
		self.assertEquals(len(result), 0, "Should have returned no nodes.")
		result = plugin._filter_by_tags(nodes, {'runtimes': {'paasmaker.runtime.php': ['5.4']}})
		self.assertEquals(len(result), 0, "Should have returned no nodes.")

	def test_simple(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		self.create_sample_nodes(session, 10)
		instance_type = self.create_sample_application(session, 'paasmaker.runtime.php', {}, '5.3')

		self.registry.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)
		plugin = self.registry.instantiate(
			'paasmaker.placement.default',
			paasmaker.util.plugin.MODE.PLACEMENT,
			{}
		)

		plugin.choose(session, instance_type, 1, self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Placement choice was not successful.")
		self.assertEquals(len(self.nodes), 1, "Placement did not return requested number of nodes.")
		self.assertTrue(self.nodes[0].heart, "Returned node was not a heart.")
		self.assertEquals(self.nodes[0].state, constants.NODE.ACTIVE, "Returned node was not active.")

	def test_more_than_available(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		self.create_sample_nodes(session, 10)
		instance_type = self.create_sample_application(session, 'paasmaker.runtime.php', {}, '5.3')

		self.registry.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)
		plugin = self.registry.instantiate(
			'paasmaker.placement.default',
			paasmaker.util.plugin.MODE.PLACEMENT,
			{}
		)

		# Request more than we have available.
		plugin.choose(session, instance_type, 20, self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Placement choice was not successful.")
		self.assertEquals(len(self.nodes), 20, "Placement did not return requested number of nodes.")
		self.assertTrue(self.nodes[0].heart, "Returned node was not a heart.")
		self.assertEquals(self.nodes[0].state, constants.NODE.ACTIVE, "Returned node was not active.")

	def test_no_runtime(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		self.create_sample_nodes(session, 10)
		instance_type = self.create_sample_application(session, 'paasmaker.runtime.noexist', {}, '1.0')

		self.registry.register(
			'paasmaker.placement.default',
			'paasmaker.pacemaker.placement.default.DefaultPlacement',
			{},
			'Default Placement'
		)
		plugin = self.registry.instantiate(
			'paasmaker.placement.default',
			paasmaker.util.plugin.MODE.PLACEMENT,
			{}
		)

		plugin.choose(session, instance_type, 1, self.success_callback, self.failure_callback)

		self.wait()

		self.assertFalse(self.success, "Placement was successful but should not have been..")
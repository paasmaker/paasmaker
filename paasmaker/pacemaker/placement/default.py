
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
	MODES = [paasmaker.util.plugin.MODE.PLACEMENT]
	OPTIONS_SCHEMA = DefaultPlacementConfigurationSchema()
	PARAMETERS_SCHEMA = DefaultPlacementParametersSchema()

	def choose(self, session, instance_type, quantity, callback, error_callback):
		# Query active nodes first.
		nodes = self.get_active_nodes(session)

		# Filter them by the tags supplied.
		tags = {}
		if self.parameters.has_key('tags'):
			tags = self.parameters['tags']
		nodes = self.filter_by_tags(nodes, tags)

		# Now choose quantity number of nodes.
		nodes = random.sample(nodes, quantity)

		callback(nodes, "Successfully located nodes.")

class DefaultPlacementTest(BasePlacementTest):

	def test_simple(self):
		session = self.configuration.get_database_session()
		self.create_sample_nodes(session, 10)

		plugin = DefaultPlacement(self.configuration, paasmaker.util.plugin.MODE.PLACEMENT, {}, {})

		# Sanity check.
		plugin.check_options()
		plugin.check_parameters()

		plugin.choose(session, None, 1, self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Placement choice was not successful.")
		self.assertEquals(len(self.nodes), 1, "Placement did not return requested number of nodes.")
		self.assertTrue(self.nodes[0].heart, "Returned node was not a heart.")
		self.assertEquals(self.nodes[0].state, constants.NODE.ACTIVE, "Returned node was not active.")
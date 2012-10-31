
import tornado.testing
import paasmaker
from paasmaker.model import Node
from paasmaker.common.core import constants

# TODO: Add logging!

# Base placement.
class BasePlacement(paasmaker.util.plugin.Plugin):

	# Helper functions for subclasses.
	def get_active_nodes(self, session):
		"""
		Get a list of active nodes from the database that are hearts.
		Returns a mutable list that you could then filter down.
		"""
		nodes = session.query(Node).\
			filter(Node.state == constants.NODE.ACTIVE, Node.heart == True)
		# Hydrate them into a real list, so it can be mutated.
		# This will be expensive. TODO: Optimise!
		result_list = []
		for node in nodes:
			result_list.append(node)

		return result_list

	def filter_by_tags(self, nodes, tags):
		"""
		Filter the given node list by the supplied tags dict.
		To match, the node must have all the tags present in
		the supplied tags and they must be equal. If the tags
		supplied is empty, then all nodes are returned.
		"""
		# Short circuit: return the nodes if no tags supplied.
		if len(tags.keys()) == 0:
			return nodes

		# Otherwise, check all the nodes.
		result_list = []
		our_keys = set(tags.keys())
		for node in nodes:
			# Figure out which keys we have in common.
			node_tags = node.tags
			their_keys = set(node_tags.keys())

			intersect = our_keys.intersection(their_keys)

			if len(intersect) == len(our_keys):
				# Can be a match. Check the keys.
				matches = True
				for key in intersect:
					if tags[key] != node_tags[key]:
						matches = False

				if matches:
					result_list.append(node)

		return result_list


	def choose(self, session, instance_type, quantity, callback, error_callback):
		"""
		Select quantity nodes to run the given instance type application.
		"""
		pass

class BasePlacementTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePlacementTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.nodes = None
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BasePlacementTest, self).tearDown()

	def success_callback(self, nodes, message):
		self.success = True
		self.message = message
		self.nodes = nodes
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.nodes = None
		self.stop()

	def create_sample_nodes(self, session, quantity):
		test_items = []
		ctr = 0
		for i in range(quantity):
			ctr += 1
			# Active heart node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.ACTIVE)
			n.heart = True
			test_items.append(n)
			ctr += 1
			# Active pacemaker node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.ACTIVE)
			n.pacemaker = True
			test_items.append(n)
			ctr += 1
			# Inactive heart node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.INACTIVE)
			n.heart = True
			test_items.append(n)
			ctr += 1
			# Active heard node with test tags.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.ACTIVE)
			n.pacemaker = True
			n.tags = {'foo': 'bar', 'test': 'three'}
			test_items.append(n)

		session.add_all(test_items)
		session.commit()
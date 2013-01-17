
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
		Returns a mutable list that you could then filter down. They
		are ordered by their score.
		"""
		nodes = session.query(
			Node
		).filter(
			Node.state == constants.NODE.ACTIVE,
			Node.heart == True
		).order_by(
			Node.score.asc()
		).all()

		return nodes

	def filter_by_tags(self, nodes, tags):
		"""
		Filter the given node list by the supplied tags dict.
		To match, the node must have all the tags present in
		the supplied tags and they must be equal. If the tags
		supplied is empty, then all nodes are returned.

		:arg list nodes: The raw list of nodes.
		:arg dict tags: The tags to compare against.
		"""
		# Short circuit: return the nodes if no tags supplied.
		if len(tags.keys()) == 0:
			return nodes

		# Otherwise, check all the nodes.
		result_list = []
		ftzr = paasmaker.util.flattenizr.Flattenizr()
		for node in nodes:
			if ftzr.compare(node.tags, tags):
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
		self.registry = self.configuration.plugins
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

	def create_sample_application(self, session, runtime_name, runtime_parameters, runtime_version):
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
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

		session.add(instance_type)
		session.commit()

		return instance_type

	def create_sample_nodes(self, session, quantity):
		test_items = []
		tagsets = [
			{
				'node': {
					'foo': 'bar',
					'test': 'three'
				},
				'runtimes': {
					'paasmaker.runtime.php': ['5.3', '5.3.10'],
					'paasmaker.runtime.ruby': ['1.9.3']
				}
			},
			{
				'node': {},
				'runtimes': {}
			},
			{
				'node': {
					'foo': 'bar',
					'test': 'three'
				},
				'runtimes': {
					'paasmaker.runtime.php': ['5.4', '5.4.4']
				}
			},
			{
				'node': {
					'foo': 'bar',
					'test': 'three'
				},
				'runtimes': {
					'paasmaker.runtime.shell': ['1']
				}
			}
		]
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
			n.tags = tagsets[(ctr - 1) % len(tagsets)]
			test_items.append(n)
			ctr += 1
			# Active pacemaker node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.ACTIVE)
			n.pacemaker = True
			n.tags = tagsets[(ctr - 1) % len(tagsets)]
			test_items.append(n)
			ctr += 1
			# Inactive heart node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.INACTIVE)
			n.heart = True
			n.tags = tagsets[(ctr - 1) % len(tagsets)]
			test_items.append(n)
			ctr += 1
			# Active pacemaker and heart node.
			n = Node(name='test%d' % ctr,
					route='%d.test.paasmaker.com' % ctr,
					apiport=888,
					uuid='%s-uuid' % ctr,
					state=constants.NODE.ACTIVE)
			n.pacemaker = True
			n.heart = True
			n.tags = tagsets[(ctr - 1) % len(tagsets)]
			test_items.append(n)

		session.add_all(test_items)
		session.commit()
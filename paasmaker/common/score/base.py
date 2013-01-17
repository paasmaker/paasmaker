
import paasmaker

import tornado.testing
import colander

class BaseScoreConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseScore(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.NODE_SCORE: None
	}
	OPTIONS_SCHEMA = BaseScoreConfigurationSchema()

	def score(self, stats):
		"""
		From the given stats dict, calculate a score for the node.
		It should be between 0 and 1 (fractional), but you can emit
		values bigger than 1 to really emphasise that the node is overloaded.
		"""
		raise NotImplementedError("You must implement score().")

class BaseScoreTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseScoreTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseScoreTest, self).tearDown()
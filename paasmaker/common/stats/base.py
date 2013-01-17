
import paasmaker

import tornado.testing
import colander

class BaseStatsConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseStats(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.NODE_STATS: None
	}
	OPTIONS_SCHEMA = BaseStatsConfigurationSchema()

	def stats(self, existing_stats):
		"""
		Alter or insert into the provided existing stats array. Return nothing.
		This is called synchronously, so you won't want to spend too long doing
		things.
		"""
		raise NotImplementedError("You must implement stats().")

class BaseStatsTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseStatsTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseStatsTest, self).tearDown()
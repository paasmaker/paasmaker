
import tornado.testing
import paasmaker

class BasePrepare(paasmaker.util.plugin.PluginMixin):

	def prepare(self, callback, error_callback):
		raise NotImplementedError("You must implement prepare()")

class BasePrepareTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePrepareTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BasePrepareTest, self).tearDown()
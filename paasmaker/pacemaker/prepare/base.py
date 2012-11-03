
import tornado.testing
import paasmaker
import tempfile
import shutil

class BasePrepare(paasmaker.util.plugin.Plugin):

	def prepare(self, environment, directory, callback, error_callback):
		raise NotImplementedError("You must implement prepare()")

class BasePrepareTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePrepareTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.success = None
		self.message = None
		self.tempdir = tempfile.mkdtemp()

	def tearDown(self):
		shutil.rmtree(self.tempdir)
		self.configuration.cleanup()
		super(BasePrepareTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.stop()
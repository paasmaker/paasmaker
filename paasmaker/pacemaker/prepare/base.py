
import tornado.testing
import paasmaker
import tempfile
import shutil

class BasePrepare(paasmaker.util.plugin.Plugin):

	def prepare(self, environment, directory, callback, error_callback):
		raise NotImplementedError("You must implement prepare()")

	def abort(self):
		"""
		Helper function called by the code that invoked this preparer, indicating
		that it should abort it's processing and clean up, if it can.

		Subclasses should override ``_abort()`` instead of this function.
		"""
		self.aborted = True

		self._abort()

	def _abort(self):
		# By default... do nothing.
		pass

class BasePrepareTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePrepareTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
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
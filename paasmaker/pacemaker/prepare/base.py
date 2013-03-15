
import tornado.testing
import paasmaker
import tempfile
import shutil

class BasePrepare(paasmaker.util.plugin.Plugin):
	"""
	These plugins prepare a source tree in some way. The most used preparer
	is the ShellPrepare, which runs a series of bash shell commands against
	the source tree to get it ready.
	"""

	def prepare(self, environment, directory, callback, error_callback):
		"""
		Prepare the supplied directory.

		Using the supplied environment, perform your work against the source
		tree, using the user supplied parameters. Call the callback once done.

		:arg dict environment: The execution environment. Pass this as ``env=environment``
			to any sub process that you invoke to ensure that runtimes are looked
			up correctly.
		:arg str directory: The directory to work on.
		:arg callable callback: The callback to call once done.
		:arg callback error_callback: The callback to call if something goes
			wrong.
		"""
		raise NotImplementedError("You must implement prepare()")

	def abort(self):
		"""
		Helper function called by the code that invoked this preparer, indicating
		that it should abort it's processing and clean up, if it can.

		Subclasses should override ``_abort()`` instead of this function, and then
		stop what they are doing.
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
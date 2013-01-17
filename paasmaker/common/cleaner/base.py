
import paasmaker

import tornado.testing
import colander

class BaseCleanerConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseCleaner(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.CLEANER: None
	}
	OPTIONS_SCHEMA = BaseCleanerConfigurationSchema()

	def clean(self, callback, error_callback):
		"""
		Perform your cleanup tasks. You must cooperate with the IO loop
		if your tasks will take some time or be IO bound. Call the callback
		with a message when complete, or the error_callback if you failed
		for some critical reason.

		If you don't need to run (for example, if the task is not appropriate
		for your node type) just call the normal callback with a message to
		that effect, rather than using the error_callback.
		"""
		raise NotImplementedError("You must implement clean().")

class BaseCleanerTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseCleanerTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.success = False
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseCleanerTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.exception = None
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()
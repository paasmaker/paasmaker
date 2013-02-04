
import paasmaker

import tornado.testing
import colander

class BasePeriodicConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BasePeriodic(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.PERIODIC: None
	}
	OPTIONS_SCHEMA = BasePeriodicConfigurationSchema()

	def on_interval(self, callback, error_callback):
		"""
		Perform your periodic tasks. You must cooperate with the IO loop
		if your tasks will take some time or be IO bound. Call the callback
		with a message when complete, or the error_callback if you failed
		for some critical reason.
		"""
		raise NotImplementedError("You must implement on_interval().")

class BasePeriodicTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BasePeriodicTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.success = False
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BasePeriodicTest, self).tearDown()

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
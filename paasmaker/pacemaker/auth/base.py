
import tornado.testing
import paasmaker

# Base user.
class BaseAuth(paasmaker.util.plugin.Plugin):

	NO_USER = 1
	BAD_AUTH = 2

	def authenticate(self, session, username, password, callback, error_callback):
		"""
		Authenticate the given user, returning a user record.
		If the user is valid and should have a local record, you can
		create that user with the supplied session and return that user.
		"""
		raise NotImplementedError("You must implement authenticate().")

class BaseAuthTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseAuthTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.user = None
		self.success = None
		self.error_reason = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseAuthTest, self).tearDown()

	def success_callback(self, user, message):
		self.success = True
		self.message = message
		self.error_reason = None
		self.user = user
		self.stop()

	def failure_callback(self, error_reason, message):
		self.success = False
		self.message = message
		self.error_reason = error_reason
		self.user = None
		self.stop()
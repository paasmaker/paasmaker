
import tornado.testing
import paasmaker

# Base user.
class BaseAuth(paasmaker.util.plugin.Plugin):
	"""
	These plugins take a raw username and password, and validate them
	against an appropriate database to determine if a user is permitted
	or not.

	Currently, the only plugin of this type is the internal authentication,
	which checks the Paasmaker database to lookup users. In future, plugins
	of this type will be able to offer looking up users in other systems,
	such as LDAP databases.
	"""

	NO_USER = 1
	BAD_AUTH = 2
	INTERNAL_ERROR = 3

	def authenticate(self, session, username, password, callback, error_callback):
		"""
		Authenticate the given user, returning a user record.
		If the user is valid and should have a local record, you can
		create that user with the supplied session and return that user.

		The callback on success looks like this::

			# 'user' is a paasmaker.model.User ORM object.
			callback(user, "Message")

		Or on failure, use one of the constants on this class to
		indicate why it failed::

			error_callback(BaseAuth.NO_USER, "Message")

		:arg Session session: An active database session.
		:arg str username: The raw username supplied by the user.
		:arg str password: The raw password supplied by the user.
		:arg callable callback: The callback to call when authenticated.
		:arg callable error_callback: The callback to call when unable to
			authenticate the user, or another error occurs.
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
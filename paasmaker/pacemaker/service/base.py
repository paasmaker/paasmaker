
import uuid
import re
import time

import tornado.testing
import paasmaker

# Base service.
class BaseService(paasmaker.util.plugin.Plugin):

	def create(self, name, callback, error_callback):
		"""
		Create the service, using the parameters supplied by the application.

		:arg str name: The user-selected name for the service. If possible,
			use that name when creating the service - you can use the helper
			function ``_safe_name()`` to make it safe for many uses.
		:arg callable callback: The callback to call once created. It
			should be supplied with two arguments; a dict of credentials
			that the application uses to connect with, and a string message.
		:arg callable error_callback: A callback to call if an error occurs.
		"""
		raise NotImplementedError("You must implement create().")

	def update(self, name, existing_credentials, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense.

		:arg str name: The user-selected name for the service.
		:arg dict existing_credentials: The existing service credentials.
		:arg callable callback: The callback to call with updated credentials.
		:arg error_callback: The error callback in case something goes wrong.
		"""
		callback(existing_credentials, "No changes required.")

	def remove(self, name, existing_credentials, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.

		:arg str name: The user-supplied name for the service.
		:arg dict existing_credentials: The existing service credentials.
		:arg callable callback: The callback to call once complete. Supply
			it a single argument; a string with a message.
		:arg callable error_callback: The callback to call if an error
			occurs.
		"""
		raise NotImplementedError("You must implement remove().")

	def _safe_name(self, name, max_length=50):
		"""
		Internal helper function to clean a user-supplied service name.
		Please make sure this produces clean names for your particular
		service before using it.

		It takes these actions:

		* Converts the service name to lower case.
		* Strips any characters other than [A-Za-z0-9].
		* Appends 8 characters of a new UUID to the name.
		* Limits the length to the given max length. It will
		  remove parts of the name to ensure that all of the
		  unique characters appear in the output.

		:arg str name: The service name.
		:arg int max_length: The maximum length of the output. The name
			is not longer than this length.
		"""
		unique = str(uuid.uuid4())[0:8]
		clean_name = re.sub(r'[^A-Za-z0-9]', '', name)
		clean_name = clean_name.lower()

		if len(clean_name) + len(unique) > max_length:
			# It'll be too long if we add the name + unique together.
			# Clip the name.
			clean_name = clean_name[0:max_length - len(unique)]

		output_name = "%s%s" % (clean_name, unique)

		return output_name

	def _generate_password(self, max_length=50):
		"""
		Internal helper function to generate a random password for you.
		It internally generates a 36 character UUID and returns that,
		which should be unique and random enough for most purposes. It
		uses Python's uuid4() which is based on random numbers.

		:arg int max_length: The maximum length of the password. The
			UUID is trimmed if needed to make it fit in this length.
		"""
		password = str(uuid.uuid4())

		if len(password) > max_length:
			password = password[0:max_length]

		return password

class BaseServiceTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseServiceTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.credentials = None
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseServiceTest, self).tearDown()

	def success_callback(self, credentials, message):
		self.success = True
		self.message = message
		self.credentials = credentials
		self.stop()

	def success_remove_callback(self, message):
		self.success = True
		self.message = message
		self.credentials = None
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.credentials = None
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()
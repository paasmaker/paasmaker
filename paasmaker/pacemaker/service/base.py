
import uuid
import re
import time

import tornado.testing
import paasmaker

# Base service.
class BaseService(paasmaker.util.plugin.Plugin):

	def create(self, name, callback, error_callback):
		"""
		Create the service, using the parameters supplied by the application
		in the request object.
		"""
		pass

	def update(self, name, existing_credentials, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense.
		"""
		pass

	def remove(self, name, existing_credentials, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.
		"""
		pass

	def _safe_name(self, name, max_length=50):
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
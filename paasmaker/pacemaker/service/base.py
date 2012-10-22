
import unittest
import tornado.testing
import paasmaker

# Base service.
class BaseService(paasmaker.util.plugin.PluginMixin):

	def get_server_configuration_schema(self):
		"""
		Get the colander schema for validating the incoming server-level
		options. That is, the options used to later provide the service.
		"""
		pass

	def get_parameters_schema(self):
		"""
		Get the colander schema for validating the
		incoming parameters. That is, the parameters required to provision
		the service.
		"""
		pass

	def get_information(self):
		"""
		Get information about this particular service.
		"""
		pass

	def create(self, callback, error_callback):
		"""
		Create the service, using the parameters supplied by the application
		in the request object.
		"""
		pass

	def update(self, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense.
		"""
		pass

	def remove(self, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.
		"""
		pass

class BaseServiceTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseServiceTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
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

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.credentials = None
		self.stop()
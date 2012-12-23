
import uuid
import os
import re

import paasmaker

import tornado
import tornado.testing
import colander

# You should subclass this configuration schema to add your own
# options.
class BaseHealthCheckConfigurationSchema(colander.MappingSchema):
	priority = colander.SchemaNode(colander.Integer(),
		title="Priority of this check",
		description="Priority of this health check. Health checks with the same priority run in parallel, and health checks with lower priorites run first.",
		default=50,
		missing=50)

class BaseHealthCheck(paasmaker.util.plugin.Plugin):
	# These are defaults - you should set your own.
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: None,
	}
	OPTIONS_SCHEMA = BaseHealthCheckConfigurationSchema()

	def check(self, callback, error_callback):
		"""
		Check what you need to check on the system, and then call the callback
		when you're complete. Call the error_callback when something goes
		seriously wrong - it's not for if there is an issue with the system.
		The idea is that you should queue up more corrective jobs onto this
		job if you need to fix something.
		"""
		raise NotImplementedError("You must implement check().")

class BaseHealthCheckTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseHealthCheckTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.path = None
		self.params = {}
		self.success = None
		self.message = None
		self.exception = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseHealthCheckTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.path = path
		self.params = params
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.path = None
		self.stop()

import uuid
import os
import re

import paasmaker

import tornado
import tornado.testing
import colander

class BaseHealthCheckConfigurationSchema(colander.MappingSchema):
	# Default is an empty set of parameters (ie, none)
	pass

class BaseHealthCheckParametersSchema(colander.MappingSchema):
	# Default is an empty set of parameters (ie, none)
	pass

class BaseHealthCheck(paasmaker.util.plugin.Plugin):
	# These are defaults - you should set your own.
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: BaseHealthCheckParametersSchema(),
	}
	OPTIONS_SCHEMA = BaseHealthCheckConfigurationSchema()

	def check(self, parent_job_id, callback, error_callback):
		"""
		Check what you need to check on the system, and then call the callback
		when you're complete. Call the error_callback when something goes
		seriously wrong - it's not for if there is an issue with the system.
		The idea is that you should queue up more corrective jobs onto the given
		parent_job_id if you need to take any corrective actions.

		Call the callback with two arguments: a dict containing context
		that goes into the calling job's tree, and a message describing
		the result of the check.
		"""
		raise NotImplementedError("You must implement check().")

class BaseHealthCheckTest(tornado.testing.AsyncTestCase, paasmaker.common.testhelpers.TestHelpers):
	def setUp(self):
		super(BaseHealthCheckTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.success = None
		self.message = None
		self.context = {}
		self.exception = None

		self.configuration.job_manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseHealthCheckTest, self).tearDown()

	def success_callback(self, context, message):
		self.success = True
		self.message = message
		self.context = context
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.path = None
		self.stop()
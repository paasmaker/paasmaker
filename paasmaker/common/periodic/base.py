#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker

import tornado.testing
import colander

class BasePeriodicConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BasePeriodic(paasmaker.util.plugin.Plugin):
	"""
	Periodic plugins are jobs that run periodically. Paasmaker organises
	to run these on the schedule you have defined, and report the output
	as a job that can be seen for later auditing.

	You only need to override ``on_interval()``, and then register your plugin,
	and finally, make sure it appears in the ``periodics`` section in your
	configuration file.
	"""
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

		If you call the error_callback, it will mark the containing job
		as failed.

		:arg callable callback: The callback to call once done.
		:arg callable error_callback: A callback to call when a critical error occurs.
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
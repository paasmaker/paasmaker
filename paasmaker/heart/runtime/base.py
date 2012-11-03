import paasmaker

import tornado.testing

# Base runtime interface.
class BaseRuntime(paasmaker.util.plugin.Plugin):

	def get_versions(self):
		"""
		Get the versions that this runtime supports. Return an array
		of versions.
		"""
		# NOTE: This is not asynchronous, so you probably don't want to
		# spend a long time doing anything.
		pass

	def environment(self, version, environment, callback, error_callback):
		"""
		Set up any environment required to run this runtime. This assumes
		that the runtime can just do it's work via an environment. You
		should mutate the supplied environment, and call the callback
		when you're done.
		"""
		raise NotImplementedError("You must implement environment().")

	def start(self, manager, instance_id, instance, callback, error_callback):
		"""
		Start the given instance of this application. Instance is a
		dict of data from the instance manager. You should not mutate
		any of it, except for the runtime dict to keep a track of anything
		you want to know.
		"""
		raise NotImplementedError("You must implement start().")

	def stop(self, manager, instance_id, instance, callback, error_callback):
		"""
		Stop the given instance of this application.
		"""
		raise NotImplementedError("You must implement stop().")

	def status(self, manager, instance_id, instance, callback, error_callback):
		"""
		Determine the status of this instance.
		"""
		raise NotImplementedError("You must implement status().")

	def statistics(self, manager, instance_id, instance, callback, error_callback):
		"""
		Generate some application instance statistics.
		You should at least return a dict containing:
		cpu_percent: CPU usage, percent, most recent.
		memory: memory used, bytes.
		cpu_time: CPU usage, in seconds total.
		If you're unable to gather this information, return zero
		for the figures.
		"""
		raise NotImplementedError("You must implement statistics().")

class BaseRuntimeTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseRuntimeTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['heart'], io_loop=self.io_loop)

		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseRuntimeTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.stop()
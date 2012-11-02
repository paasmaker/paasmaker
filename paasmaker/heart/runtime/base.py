import paasmaker
import unittest

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

	def start(self, manager, instance_id, instance, callback, error_callback):
		"""
		Start the given instance of this application. Instance is a
		dict of data from the instance manager. You should not mutate
		any of it, except for the runtime dict to keep a track of anything
		you want to know.
		"""
		raise NotImplementedError("You must implement start.")

	def stop(self, manager, instance_id, instance, callback, error_callback):
		"""
		Stop the given instance of this application.
		"""
		raise NotImplementedError("You must implement stop.")

	def status(self, manager, instance_id, instance, callback, error_callback):
		"""
		Determine the status of this instance.
		"""
		raise NotImplementedError("You must implement stop.")

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
		raise NotImplementedError("You must implement stop.")

class BaseRuntimeTest(unittest.TestCase):
	def setUp(self):
		# TODO: Create an appropriate configuration stub.
		self.registry = paasmaker.util.plugin.PluginRegistry({})

	def tearDown(self):
		# TODO: Clean up the configuration stub, when that's implemented.
		pass
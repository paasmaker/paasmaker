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

	def check_system(self):
		"""
		Confirm that the system is able to run this runtime.
		"""
		raise NotImplementedError("You must implement check_system.")

	def start(self, instance):
		"""
		Start the given instance of this application.
		"""
		raise NotImplementedError("You must implement start.")

	def stop(self, instance):
		"""
		Stop the given instance of this application.
		"""
		raise NotImplementedError("You must implement stop.")

	def status(self, instance):
		"""
		Determine the status of this instance.
		"""
		raise NotImplementedError("You must implement stop.")

	def statistics(self, instance):
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
# Base runtime interface.
class RuntimeBase():
	def __init__(self, configuration):
		self.configuration = configuration

	def get_server_configuration_schema(self):
		"""
		Get the colander schema for validating the incoming server-level
		options. That is, the options used to later run the application.
		"""
		pass

	def get_application_configuration_schema(self):
		"""
		Get the colander schema for validating the
		incoming application-level options. That is, the options
		required to run the application later.
		"""
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

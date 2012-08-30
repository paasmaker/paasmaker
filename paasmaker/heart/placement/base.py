# Application placement strategy - base class.

class Base():
	def __init__(self, configuration):
		self.configuration = configuration

	def get_application_configuration_schema(self):
		"""
		Get the dotconf schema for validating the
		incoming application-level options. That is, the options
		required to determine where this instance is placed.
		"""
		pass

	def filter_by_runtime(self, instance, nodes):
		"""
		Filter the list of nodes by the runtime.
		"""
		pass

	def mark_already_running(self, instance, nodes):
		"""
		Mark nodes as already running the given instance
		if they are already running the given instance.
		"""
		pass

	def choose(self, instance, nodes):
		"""
		From the given nodes, attempt to choose a node to place the
		given instance.
		"""
		raise NotImplementedError("You must implement choose().")

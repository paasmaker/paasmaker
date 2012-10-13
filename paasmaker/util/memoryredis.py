
from paasmaker.util.managedredis import ManagedRedis
import tempfile

class MemoryRedis(ManagedRedis):
	def __init__(self, configuration):
		super(MemoryRedis, self).__init__(configuration)

		temp_dir = tempfile.mkdtemp()
		self.configure(temp_dir, self.configuration.get_free_port(), '127.0.0.1')

import paasmaker

class NodeRegisterAPIRequest(paasmaker.util.APIRequest):

	def register(self):
		# Build our payload.
		payload = {}
		# Insert: our port
		# Insert: heart - our runtimes.
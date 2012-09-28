
import paasmaker

class NodeRegisterAPIRequest(paasmaker.util.APIRequest):

	def build_payload(self):
		# Build our payload.
		payload = {}
		payload['name'] = self.configuration.get_flat('my_name')
		payload['route'] = self.configuration.get_flat('my_route')
		payload['apiport'] = self.configuration.get_flat('http_port')

		if self.configuration.is_heart():
			runtimes = []
			payload['runtimes'] = runtimes

		return payload

	def get_endpoint(self):
		return '/node/register'

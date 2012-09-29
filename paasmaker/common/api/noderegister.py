
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterAPIRequest(paasmaker.util.APIRequest):

	def build_payload(self):
		# Build our payload.
		payload = {}
		payload['name'] = self.configuration.get_flat('my_name')
		payload['route'] = self.configuration.get_flat('my_route')
		payload['apiport'] = self.configuration.get_flat('http_port')

		# TODO: Implement/send tags!

		if self.configuration.is_heart():
			# TODO: Send runtimes list!
			runtimes = []
			payload['runtimes'] = runtimes

		return payload

	def get_endpoint(self):
		return '/node/register'

	def process_response(self, response):
		if response.success:
			# Save our nodes UUID.
			self.configuration.set_node_uuid(response.data['node']['uuid'])
		else:
			logger.error("Unable to register with master!")
			for error in response.errors:
				logger.error(error)

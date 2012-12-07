
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterAPIRequest(paasmaker.util.APIRequest):

	def build_payload(self):
		# Build our payload.
		payload = {}

		# So here's my number... call me maybe?
		payload['name'] = self.configuration.get_flat('my_name')
		payload['route'] = self.configuration.get_flat('my_route')
		payload['apiport'] = self.configuration.get_flat('http_port')

		# Send along the node tags.
		tags = {}

		# The node roles.
		roles = {}
		roles['heart'] = self.configuration.is_heart()
		roles['pacemaker'] = self.configuration.is_pacemaker()
		roles['router'] = self.configuration.is_router()

		tags['roles'] = roles

		# Runtimes.
		if self.configuration.is_heart():
			runtimes = self.configuration.get_runtimes()
			tags['runtimes'] = runtimes

		# Include node tags.
		tags['node'] = self.configuration['tags']

		payload['tags'] = tags

		logger.debug("Sending node tags: %s", str(tags))

		# For hearts, send along instance statuses.
		if self.configuration.is_heart():
			statuses = self.configuration.instances.get_instance_list()
			payload['instances'] = statuses

			logger.debug("Sending instance states: %s", str(statuses))

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

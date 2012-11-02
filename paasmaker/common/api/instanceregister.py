
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# NOTE: Only suitable for use by a Pacemaker.
class InstanceRegisterAPIRequest(paasmaker.util.APIRequest):

	def set_instance(self, instance):
		self.instance = instance

	def build_payload(self):
		# Build our payload.
		payload = self.instance.flatten_for_heart()
		return payload

	def get_endpoint(self):
		return '/instance/register'

	def process_response(self, response):
		if response.success:
			logger.info("Registered instance %s with node.", self.instance.instance_id)

			# Store the port that was returned in the instance.
			session = self.configuration.get_database_session()

			instance = session.query(paasmaker.model.ApplicationInstance).get(self.instance.id)
			instance.port = response.data['port']
			session.add(instance)
			session.commit()

			# TODO: Handle the returned job ID...

			logger.info("Stored instance port %d for instance %s.", instance.port, instance.instance_id)
		else:
			logger.error("Unable to register instance:")
			for error in response.errors:
				logger.error(error)

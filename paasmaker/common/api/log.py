
import logging

import paasmaker
from apirequest import APIRequest, StreamAPIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Stream logs back to the client.
class LogStreamAPIRequest(StreamAPIRequest):

	def subscribe(self, job_id, position=0):
		logging.debug("Subscribing to %s", job_id)
		self.send_message('subscribe', {'job_id': job_id, 'position': position})

	def unsubscribe(self, job_id):
		logging.debug("Unsubscribing from %s", job_id)
		self.send_message('unsubscribe', {'job_id': job_id})

	def get_endpoint(self):
		return '/log/stream'
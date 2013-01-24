
import logging

import paasmaker
from apirequest import APIRequest, StreamAPIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobAbortAPIRequest(APIRequest):
	"""
	Send an abort request to a specific job ID.
	"""
	def __init__(self, *args, **kwargs):
		super(JobAbortAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'
		self.job_id = None

	def set_job(self, job_id):
		"""
		Set the ID of the job to abort.

		:arg str job_id: The job ID to abort.
		"""
		self.job_id = job_id

	def get_endpoint(self):
		return '/job/abort/%s' % self.job_id


class JobStreamAPIRequest(StreamAPIRequest):

	def subscribe(self, job_id):
		logging.debug("Subscribing to %s", job_id)
		self.send_message('subscribe', {'job_id': job_id})

	def unsubscribe(self, job_id):
		logging.debug("Unsubscribing from %s", job_id)
		self.send_message('unsubscribe', {'job_id': job_id})

	def get_endpoint(self):
		return '/job/stream'
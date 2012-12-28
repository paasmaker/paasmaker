
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

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
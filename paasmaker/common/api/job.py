
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobAbortAPIRequest(APIRequest):
	def __init__(self, *args, **kwargs):
		super(JobAbortAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'
		self.job_id = None

	def set_job(self, job_id):
		self.job_id = job_id

	def get_endpoint(self):
		return '/job/abort/%s' % self.job_id
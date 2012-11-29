
import logging

import paasmaker

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeListAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(NodeListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/node/list'
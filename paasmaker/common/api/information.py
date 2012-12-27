
import paasmaker

from apirequest import APIRequest, APIResponse

class InformationAPIRequest(APIRequest):
	"""
	Fetch basic information on a node. Designed for use internally
	to make sure the node can be contacted.
	"""

	def get_endpoint(self):
		return '/information'
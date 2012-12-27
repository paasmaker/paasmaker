
import paasmaker

from apirequest import APIRequest, APIResponse

class InformationAPIRequest(APIRequest):
	def get_endpoint(self):
		return '/information'

import paasmaker

class InformationAPIRequest(paasmaker.util.APIRequest):
	def get_endpoint(self):
		return '/information'
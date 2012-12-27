
import paasmaker
from apirequest import APIRequest, APIResponse

class LoginAPIRequest(APIRequest):
	def set_credentials(self, username, password):
		self.username = username
		self.password = password

	def build_payload(self):
		return {'username': self.username, 'password': self.password}

	def get_endpoint(self):
		return '/login'

import paasmaker
from apirequest import APIRequest, APIResponse

class LoginAPIRequest(APIRequest):
	"""
	Requests a login from the system. The username and password
	are transmitted in clear text. Intended mainly for testing
	purposes.
	"""

	def set_credentials(self, username, password):
		"""
		Set the credentials for this request.

		:arg str username: The username.
		:arg str password: The clear text password.
		"""
		self.username = username
		self.password = password

	def build_payload(self):
		return {'username': self.username, 'password': self.password}

	def get_endpoint(self):
		return '/login'
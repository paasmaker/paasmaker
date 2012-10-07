
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UserCreateAPIRequest(paasmaker.util.APIRequest):
	def set_params(self, name, login, email, enabled):
		self.params = {}
		self.params['name'] = name
		self.params['login'] = login
		self.params['email'] = email
		self.params['enabled'] = enabled

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/user/create'

class UserEditAPIRequest(paasmaker.util.APIRequest):
	def set_user(self, user_id):
		self.user_id = user_id

	def get_endpoint(self):
		return "/user/edit/%d" % self.user_id
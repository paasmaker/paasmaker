
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UserGetAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(UserGetAPIRequest, self).__init__(*args, **kwargs)
		self.user_id = None
		self.method = 'GET'

	def set_user(self, user_id):
		self.user_id = user_id

	def get_endpoint(self):
		return '/user/%d' % self.user_id

class UserCreateAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(UserCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_user_params(self, name, login, email, enabled):
		self.params['name'] = name
		self.params['login'] = login
		self.params['email'] = email
		self.params['enabled'] = enabled

	def set_user_password(self, password):
		self.params['password'] = password

	def set_user_login(self, login):
		self.params['login'] = login

	def set_user_name(self, name):
		self.params['name'] = name

	def set_user_enabled(self, enabled):
		self.params['enabled'] = enabled

	def set_user_email(self, email):
		self.params['email'] = email

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/user/create'

class UserEditAPIRequest(UserCreateAPIRequest):
	def __init__(self, *args, **kwargs):
		super(UserEditAPIRequest, self).__init__(*args, **kwargs)
		self.user_id = None

	def set_user(self, user_id):
		self.user_id = user_id

	def load(self, user_id, callback):
		request = UserGetAPIRequest(self.configuration)
		request.duplicate_auth(self)
		request.set_user(user_id)
		def on_load_complete(response):
			logger.debug("Loading complete.")
			if response.success:
				self.params.update(response.data['user'])
				self.user_id = self.params['id']
				logger.debug("Loading complete for user %d", self.user_id)
				callback(response)
			else:
				logger.debug("Loading failed for user.")
				callback(response)
		request.send(on_load_complete)
		logger.debug("Awaiting results of load from the server.")

	def get_endpoint(self):
		return "/user/%d" % self.user_id

class UserListAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(UserListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/user/list'
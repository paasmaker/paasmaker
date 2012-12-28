
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UserGetAPIRequest(APIRequest):
	"""
	Get the details for a user.
	"""
	def __init__(self, *args, **kwargs):
		super(UserGetAPIRequest, self).__init__(*args, **kwargs)
		self.user_id = None
		self.method = 'GET'

	def set_user(self, user_id):
		"""
		Set the user ID to fetch details for.

		:arg int user_id: The user ID to fetch.
		"""
		self.user_id = user_id

	def get_endpoint(self):
		return '/user/%d' % self.user_id

class UserCreateAPIRequest(APIRequest):
	"""
	Create a new user. You will need to be authenticated
	using the super token, or another user with appropriate
	privileges.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(UserCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_user_params(self, name, login, email, enabled):
		"""
		Set all of the user parameters at once.

		:arg str name: The user's name.
		:arg str login: The user's login handle.
		:arg str email: The user's email address.
		:arg bool enabled: If the user is enabled.
		"""
		self.params['name'] = name
		self.params['login'] = login
		self.params['email'] = email
		self.params['enabled'] = enabled

	def set_user_password(self, password):
		"""
		Set the user's password. If this is not called,
		no password is sent to the server. For update
		requests, that means that the password remains
		unchanged. For create requests, the request will
		fail with an error.

		:arg str password: The cleartext password.
		"""
		self.params['password'] = password

	def set_user_login(self, login):
		"""
		Set the user's login.

		:arg str login: The user's login.
		"""
		self.params['login'] = login

	def set_user_name(self, name):
		"""
		Set the user's name.

		:arg str name: The user's name.
		"""
		self.params['name'] = name

	def set_user_enabled(self, enabled):
		"""
		Set the user's enabled flag.

		:arg bool enabled: The user's enabled flag.
		"""
		self.params['enabled'] = enabled

	def set_user_email(self, email):
		"""
		Set the user's email address.

		:arg str email: The user's email address.
		"""
		self.params['email'] = email

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/user/create'

class UserEditAPIRequest(UserCreateAPIRequest):
	"""
	Edit an existing user. This class is a subclass of
	UserCreateAPIRequest, so once the user is loaded,
	the functions inherited from the class can be used
	to mutate the user.
	"""
	def __init__(self, *args, **kwargs):
		super(UserEditAPIRequest, self).__init__(*args, **kwargs)
		self.user_id = None

	def set_user(self, user_id):
		"""
		Set the user ID to edit.
		"""
		self.user_id = user_id

	def load(self, user_id, callback, error_callback):
		"""
		Load the user from the server, calling the callback
		with data from the user. The data is also stored
		inside the class, ready to be mutated and sent
		back to the server.

		As this is a subclass of UserCreateAPIRequest, you can
		use the mutators on that class to modify the user.

		:arg int user_id: The user ID to load.
		:arg callable callback: The callback to call on success.
		:arg callable error_callback: The error callback on failure.
		"""
		request = UserGetAPIRequest(self.configuration)
		request.duplicate_auth(self)
		request.set_user(user_id)
		def on_load_complete(response):
			logger.debug("Loading complete.")
			if response.success:
				self.params.update(response.data['user'])
				self.user_id = self.params['id']
				logger.debug("Loading complete for user %d", self.user_id)
				callback(response.data['user'])
			else:
				logger.debug("Loading failed for user.")
				error_callback(str(response.errors))
		request.send(on_load_complete)
		logger.debug("Awaiting results of load from the server.")

	def get_endpoint(self):
		return "/user/%d" % self.user_id

class UserListAPIRequest(APIRequest):
	"""
	List all the users in the system.
	"""
	def __init__(self, *args, **kwargs):
		super(UserListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/user/list'
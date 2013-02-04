
from base import BaseAuth, BaseAuthTest
from internal import InternalAuth
import paasmaker

import colander

class AllowAnyConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class AllowAnyAuth(InternalAuth):
	"""
	This is a very dangerous allow any plugin. Upon the first time
	someone tries to authenticate, it creates them an account with
	the supplied password. Afterwards, they can then authenticate
	normally.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN: None
	}
	OPTIONS_SCHEMA = AllowAnyConfigurationSchema()
	API_VERSION = "0.9.0"

	def authenticate(self, session, username, password, callback, error_callback):
		# HACK: Make our instance think it's internal.
		self.called_name = 'paasmaker.auth.internal'

		# Call our parent to see if we can find any authenticate the user.
		# If so, we let that go directly back.
		# Otherwise, we create the item.
		def parent_error_callback(reason, message):
			if reason == self.NO_USER:
				# Create the user, and try again.
				user = paasmaker.model.User()
				user.login = username
				user.email = 'unknown@paasmaker.com'
				user.name = username
				user.password = password
				session.add(user)
				session.commit()

				super(AllowAnyAuth, self).authenticate(session, username, password, callback, error_callback)
			else:
				# Bad password. Propagate the failure.
				error_callback(reason, message)

		super(AllowAnyAuth, self).authenticate(
			session,
			username,
			password,
			callback,
			parent_error_callback
		)

class AllowAnyAuthTest(BaseAuthTest):

	def test_simple_success(self):
		self.registry.register(
			'paasmaker.auth.allowany',
			'paasmaker.pacemaker.auth.allowany.AllowAnyAuth',
			{},
			'Allow Any Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.allowany',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		session = self.configuration.get_database_session()

		auth.authenticate(
			session,
			'username',
			'test',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "User authentication failed.")

	def test_wrong_password(self):
		self.registry.register(
			'paasmaker.auth.allowany',
			'paasmaker.pacemaker.auth.allowany.AllowAnyAuth',
			{},
			'Allow Any Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.allowany',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		session = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		session.add(u)
		session.commit()

		auth.authenticate(
			session,
			'username',
			'wrongpassword',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertFalse(self.success, "User authentication should not have succeeded.")

	def test_right_password(self):
		self.registry.register(
			'paasmaker.auth.allowany',
			'paasmaker.pacemaker.auth.allowany.AllowAnyAuth',
			{},
			'Allow Any Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.allowany',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		session = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		session.add(u)
		session.commit()

		auth.authenticate(
			session,
			'username',
			'test',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "User authentication should have succeeded.")
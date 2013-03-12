
from base import BaseAuth, BaseAuthTest
import paasmaker

import colander

class InternalUserConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class InternalAuth(BaseAuth):
	"""
	This is the internal authentication plugin.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN: None
	}
	OPTIONS_SCHEMA = InternalUserConfigurationSchema()
	API_VERSION = "0.9.0"

	def authenticate(self, session, username, password, callback, error_callback):
		# Search for user, where the source matches our name.
		user = session.query(paasmaker.model.User) \
			.filter(paasmaker.model.User.login==username,
				paasmaker.model.User.auth_source==self.called_name).first()

		if not user:
			# No such user.
			error_callback(self.NO_USER, "No such user.")
		else:
			# Check their password.
			if user.check_password(password):
				callback(user, "Success.")
			else:
				error_callback(self.BAD_AUTH, "Invalid password.")

class InternalAuthTest(BaseAuthTest):
	def test_simple_fail(self):

		self.registry.register(
			'paasmaker.auth.internal',
			'paasmaker.pacemaker.auth.internal.InternalAuth',
			{},
			'Internal Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.internal',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		auth.authenticate(
			session,
			'test',
			'password',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertFalse(self.success, "User authentication failed.")

	def test_simple_success(self):
		self.registry.register(
			'paasmaker.auth.internal',
			'paasmaker.pacemaker.auth.internal.InternalAuth',
			{},
			'Internal Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.internal',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
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

		self.assertTrue(self.success, "User authentication failed.")
		self.assertEquals(self.user.id, u.id, "User does not match.")

	def test_wrong_password(self):
		self.registry.register(
			'paasmaker.auth.internal',
			'paasmaker.pacemaker.auth.internal.InternalAuth',
			{},
			'Internal Authentication'
		)
		auth = self.registry.instantiate(
			'paasmaker.auth.internal',
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
		)

		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
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

from base import BaseAuth, BaseAuthTest
import paasmaker

import colander

class InternalUserConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class InternalUserParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

# Parameters service.
class InternalAuth(BaseAuth):
	"""
	This is the internal authentication plugin.
	"""
	MODES = [paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN]
	OPTIONS_SCHEMA = InternalUserConfigurationSchema()
	PARAMETERS_SCHEMA = {}

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
		auth = InternalAuth(
			self.configuration,
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN,
			{},
			{},
			'paasmaker.auth.internal'
		)

		# Sanity check.
		auth.check_options()

		session = self.configuration.get_database_session()
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
		auth = InternalAuth(
			self.configuration,
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN,
			{},
			{},
			'paasmaker.auth.internal'
		)

		session = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		session.add(u)
		session.commit()

		# Sanity check.
		auth.check_options()

		auth.authenticate(
			session,
			'username',
			'test',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "User authentication succeeded.")
		self.assertEquals(self.user.id, u.id, "User does not match.")

	def test_wrong_password(self):
		auth = InternalAuth(
			self.configuration,
			paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN,
			{},
			{},
			'paasmaker.auth.internal'
		)

		session = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		session.add(u)
		session.commit()

		# Sanity check.
		auth.check_options()

		auth.authenticate(
			session,
			'username',
			'wrongpassword',
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertFalse(self.success, "User authentication should not have succeeded.")
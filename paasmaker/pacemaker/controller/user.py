import unittest
import paasmaker
import uuid
import logging
import colander
import json
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import tornado.testing

import smallform

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UserSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="User name",
		description="A nice name for this user.",
		validator=colander.Length(min=2))
	login = colander.SchemaNode(colander.String(),
		title="Login",
		description="The handle that the user uses to login.",
		validator=colander.Length(min=2))
	email = colander.SchemaNode(colander.String(),
		title="Email address",
		description="The email address of this user.",
		validator=colander.Email())
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Enabled",
		description="If this user is enabled.")
	password = colander.SchemaNode(colander.String(),
		title="Password",
		description="The users password (blank to leave unchanged)",
		default="",
		missing="",
		# TODO: more complex password requirements.
		validator=colander.Length(min=8))

class UserController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self, user_id):
		# TODO: Permissions.
		# Find and load the user.
		user = self.db().query(paasmaker.model.User).get(int(user_id))
		if not user:
			self.write_error(404, "No such user.")
		self.add_data('user', user)

		self.render("api/apionly.html")

	def post(self, user_id):
		self.get(user_id)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/(\d+)", UserController, configuration))
		return routes

class UserEditController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get_form(self, user=None):
		schema = UserSchema()
		if user:
			form = smallform.Form(schema, defaults=user.flatten())
		else:
			form = smallform.Form(schema)
		return form

	def get(self, user_id=None):
		# TODO: Permissions.
		user = None
		if user_id:
			# Find and load the user.
			user = self.db().query(paasmaker.model.User).get(int(user_id))
			if not user:
				self.write_error(404, "No such user.")
			self.add_data('user', user)

		form = self.get_form(user)
		form.validate(self.params)
		self.add_data_template('form', form)

		self.render("user/edit.html")

	def post(self, user_id=None):
		# TODO: Permissions.
		user = None
		if user_id:
			# Find and load the user.
			user = self.db().query(paasmaker.model.User).get(int(user_id))
			if not user:
				self.write_error(404, "No such user.")

		form = self.get_form(user)
		values = form.validate(self.params)
		if not form.errors:
			if not user_id:
				user = paasmaker.model.User()
				user.auth_method = "internal"
			user = form.bind(user, exclude=('password',))
			password_plain = self.param('password')
			if password_plain and password_plain != '':
				user.password = password_plain
			if not user_id and (not password_plain or password_plain == ''):
				self.add_error("No password supplied, and this is a new account.")
			else:
				session = self.db()
				session.add(user)
				session.commit()
				session.refresh(user)

				self.add_data('user', user)

				self.redirect('/user/list')
				return
		else:
			for key, message in form.errors.iteritems():
				self.add_error("%s: %s" % (key, ", ".join(message)))

		self.add_data_template('form', form)

		self.render("user/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/create", UserEditController, configuration))
		routes.append((r"/user/edit/(\d+)", UserEditController, configuration))
		return routes

class UserListController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self):
		# TODO: Permissions.
		# TODO: Paginate...
		users = self.db().query(paasmaker.model.User)
		self.add_data('users', users)
		self.render("user/list.html")

	def post(self):
		self.get()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/list", UserListController, configuration))
		return routes

class UserEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration()
		routes = UserEditController.get_routes({'configuration': self.configuration, 'io_loop': self.io_loop})
		routes.extend(UserListController.get_routes({'configuration': self.configuration, 'io_loop': self.io_loop}))
		routes.extend(UserController.get_routes({'configuration': self.configuration, 'io_loop': self.io_loop}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('user'), "Missing user object in return data.")
		self.assertTrue(response.data['user'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['user'].has_key('login'), "Missing login in return data.")
		self.assertFalse(response.data['user'].has_key('password'), "Password was present in returned data.")
		self.assertEquals(response.data['user']['enabled'], True, "User is not enabled.")

	def test_create_fail(self):
		# Send through some bogus data.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_user_params('', '', '', True)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("Required" in response.errors[0], "Missing message in error.")

		# Now update the request somewhat, but fail to set a password.
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("password" in response.errors[0], "Missing message in error.")

	def test_edit(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		user_id = response.data['user']['id']

		# Set up the request.
		request = paasmaker.common.api.user.UserEditAPIRequest(self.configuration, self.io_loop)
		# This loads the user data from the server.
		request.load(user_id, self.stop)
		load_response = self.wait()
		self.failIf(not load_response.success)

		# Now attempt to change the user.
		request.set_user_name('Test Updated')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(response.data['user']['name'], 'Test Updated', 'Name was not updated.')
		# Load up the user separately and confirm.
		user = self.configuration.get_database_session().query(paasmaker.model.User).get(user_id)
		self.assertEquals(user.name, 'Test Updated', 'Name was not updated.')

	def test_edit_fail(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		user_id = response.data['user']['id']

		# Set up the request.
		request = paasmaker.common.api.user.UserEditAPIRequest(self.configuration, self.io_loop)
		# This loads the user data from the server.
		request.load(user_id, self.stop)
		load_response = self.wait()
		self.failIf(not load_response.success)

		# Now attempt to change the user.
		request.set_user_email('foo')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("email" in response.errors[0], "Missing message in error.")

	def test_list(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.user.UserListAPIRequest(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('users'), "Missing users list.")
		self.assertEquals(len(response.data['users']), 1, "Not enough users returned.")
		self.assertEquals(response.data['users'][0]['name'], 'User Name', "Returned user is not as expected.")

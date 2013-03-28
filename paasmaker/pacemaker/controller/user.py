#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import unittest
import uuid
import logging
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import colander
import tornado
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class Boolean(object):
	def serialize(self, node, appstruct):
		if appstruct is colander.null:
			return colander.null
		if not isinstance(appstruct, bool):
		   raise Invalid(node, '%r is not a boolean')
		return appstruct and 'true' or 'false'

	def deserialize(self, node, cstruct):
		if cstruct is colander.null:
		   return colander.null
		if isinstance(cstruct, bool):
			return cstruct
		if not isinstance(cstruct, basestring):
			raise Invalid(node, '%r is not a string' % cstruct)
		value = cstruct.lower()
		if value in ('true', 'yes', 'y', 'on', 't', '1'):
			return True
		return False

	def cstruct_children(self):
		return []

	def unflatten(self, subnode, subpaths, subfstruct):
		return self.deserialize(subnode, subfstruct[subnode.name])

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
	enabled = colander.SchemaNode(Boolean(),
		title="Enabled",
		description="If this user is enabled.",
		missing=False,
		default=False)
	password = colander.SchemaNode(colander.String(),
		title="Password",
		description="The users password (blank to leave unchanged)",
		default="",
		missing="",
		# TODO: more complex password requirements.
		validator=colander.Length(min=8))

class UserEditController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_user(self, user_id=None):
		user = None
		if user_id:
			# Find and load the user.
			user = self.session.query(
				paasmaker.model.User
			).get(int(user_id))
			if not user:
				raise HTTPError(404, "No such user.")

			self.add_data('user', user)

		return user

	def _default_user(self):
		user = paasmaker.model.User()
		user.name = ''
		user.login = ''
		user.email = ''
		return user

	def get(self, user_id=None):
		self.require_permission(constants.PERMISSION.USER_EDIT)
		user = self._get_user(user_id)
		if not user:
			user = self._default_user()
			self.add_data('user', user)

		self.render("user/edit.html")

	def post(self, user_id=None):
		self.require_permission(constants.PERMISSION.USER_EDIT)
		user = self._get_user(user_id)

		valid_data = self.validate_data(UserSchema())

		if not user:
			user = self._default_user()

		user.name = self.params['name']
		user.login = self.params['login']
		user.email = self.params['email']
		user.enabled = self.params['enabled']

		if valid_data and not user.id:
			# Password must be supplied.
			if self.params['password'] == '':
				self.add_error("No password supplied.")
				valid_data = False

		if valid_data:
			if self.params.has_key('password'):
				user.password = self.params['password']

			self.session.add(user)
			self.session.commit()
			self.session.refresh(user)

			self.add_data('user', user)

			self.redirect('/user/list')
		else:
			self.add_data('user', user)
			self.render("user/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/create", UserEditController, configuration))
		routes.append((r"/user/(\d+)", UserEditController, configuration))
		return routes

class UserListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.USER_LIST)
		users = self.session.query(paasmaker.model.User)

		self._paginate('users', users)
		# self.add_data('users', users)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/list", UserListController, configuration))
		return routes

class UserEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = UserEditController.get_routes({'configuration': self.configuration})
		routes.extend(UserListController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
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
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_user_params('', '', '', True)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue('input_errors' in response.data, "Did not fail with errors.")
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('login'), "Missing error on login attribute.")
		self.assertTrue(input_errors.has_key('name'), "Missing error on login attribute.")
		self.assertTrue(input_errors.has_key('email'), "Missing error on login attribute.")

		# Now update the request somewhat, but fail to set a password.
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("password" in response.errors[0], "Missing message in error.")

	def test_edit(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		user_id = response.data['user']['id']

		# Set up the request.
		request = paasmaker.common.api.user.UserEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the user data from the server.
		request.load(user_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the user.
		request.set_user_name('Test Updated')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(response.data['user']['name'], 'Test Updated', 'Name was not updated.')
		# Load up the user separately and confirm.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = session.query(
			paasmaker.model.User
		).get(user_id)
		self.assertEquals(user.name, 'Test Updated', 'Name was not updated.')

	def test_edit_fail(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		user_id = response.data['user']['id']

		# Set up the request.
		request = paasmaker.common.api.user.UserEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the user data from the server.
		request.load(user_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the user.
		request.set_user_email('foo')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('email'), "Missing error on email attribute.")

	def test_list(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.user.UserListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('users'), "Missing users list.")
		self.assertEquals(len(response.data['users']), 1, "Not enough users returned.")
		self.assertEquals(response.data['users'][0]['name'], 'User Name', "Returned user is not as expected.")

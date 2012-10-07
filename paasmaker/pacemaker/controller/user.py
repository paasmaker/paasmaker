import unittest
import paasmaker
import uuid
import logging
import colander
import json
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import tornado.testing

import wtforms

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UserSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="User name",
		description="A nice name for this user.")
	login = colander.SchemaNode(colander.String(),
		title="Login",
		description="The handle that the user uses to login.")
	email = colander.SchemaNode(colander.String(),
		title="Email address",
		description="The email address of this user.")
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Enabled",
		description="If this user is enabled.")

class UserForm(wtforms.Form):
	username = wtforms.TextField('Name')
	login = wtforms.TextField('Login')
	email = wtforms.TextField('Email Address')
	enabled = wtforms.BooleanField('Enabled')

class UserEditController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self, action):
		# TODO: Permissions.
		if action == 'edit':
			# Find and load the user.
			raw_id = self.param('id')
			user = self.db().query(paasmaker.model.User).get(int(raw_id))
			if not user:
				self.write_error(404, "No such user.")
			self.add_data('user', user)

		self.render("user/edit.html")

	def post(self, action):
		user = paasmaker.model.User()
		user.auth_method = "internal"
		if action == 'edit':
			# Find and load the user.
			raw_id = self.param('id')
			user = self.db().query(paasmaker.model.User).get(int(raw_id))
			if not user:
				self.write_error(404, "No such user.")
		print
		print str(self.params)
		print
		form = UserForm(self.params, user)
		if form.validate():
			form.populate_obj(user)
			session = self.db()
			session.add(user)
			session.commit()

			self.add_data('user', user)

		self.add_data_template('form', form)

		self.render("user/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/user/(create|edit)", UserEditController, configuration))
		return routes

class UserListController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self, action):
		# TODO: Permissions.
		# TODO: Paginate...
		users = self.db().query(paasmaker.model.User)
		self.add_data('users', users)
		self.render("user/list.html")

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
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration, self.io_loop)
		request.set_params('Daniel Foote', 'danielf', 'freefoote@dview.net', True)
		request.send(self.stop)
		response = self.wait()

		print str(response.errors)
		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")

		self.assertEquals(self.configuration.get_node_uuid(), response.data['node'])
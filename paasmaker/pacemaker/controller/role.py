import unittest
import paasmaker
import uuid
import logging
import colander
import json

from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RoleSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Role name",
		description="A nice name for this role.",
		validator=colander.Length(min=2))

	permissions = colander.SchemaNode(colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Permissions",
		default=[],
		missing=[])

# GET /role/list - list roles
# POST /role/create - create
# GET /role/<id> - fetch role information.
# POST /role/<id> - change role.

# GET /role/allocation/list - list assigned user roles.
# POST /role/allocation/assign - assign.
# POST /role/allocation/unassign - unassign.

class RoleListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		# TODO: Permissions.
		# TODO: Pagination.
		# Find and load the user.
		roles = self.db().query(paasmaker.model.Role).all()
		self.add_data('roles', roles)

		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/list", RoleListController, configuration))
		return routes

class RoleEditController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_role(self, role_id):
		role = None
		if role_id:
			# Find and load the role.
			role = self.db().query(paasmaker.model.Role).get(int(role_id))
			if not role:
				self.add_error("No such role.")
				self.write_error(404)
		return role

	def get(self, role_id=None):
		# TODO: Permissions.
		role = self._get_role(role_id)
		self.add_data('role', role)
		self.render("role/edit.html")

	def post(self, role_id=None):
		# TODO: Permissions.
		role = self._get_role(role_id)

		if not self.validate_data(RoleSchema()):
			return

		if not role:
			role = paasmaker.model.Role()

		role.name = self.param('name')
		role.permissions = self.param('permissions')

		session = self.db()
		session.add(role)
		session.commit()
		session.refresh(role)

		self.add_data('role', role)

		self.render("role/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/create", RoleEditController, configuration))
		routes.append((r"/role/(\d+)", RoleEditController, configuration))
		return routes

class RoleEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = RoleEditController.get_routes({'configuration': self.configuration})
		routes.extend(RoleListController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_CREATE])
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('role'), "Missing role object in return data.")
		self.assertTrue(response.data['role'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['role'].has_key('permissions'), "Missing permissions in return data.")
		self.assertIn(constants.PERMISSION.USER_CREATE, response.data['role']['permissions'])

	def test_create_fail(self):
		# Send through some bogus data.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('', [])
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("Invalid" in response.errors[0], "Missing message in error.")

	def test_edit(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_CREATE])
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		role_id = response.data['role']['id']

		# Set up the request.
		request = paasmaker.common.api.role.RoleEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the role data from the server.
		request.load(role_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the role.
		request.set_role_permissions(load_response['permissions'] + [constants.PERMISSION.WORKSPACE_CREATE])

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.data['role']['permissions']), 2, 'Not enough permissions.')
		self.assertIn(constants.PERMISSION.USER_CREATE, response.data['role']['permissions'])
		self.assertIn(constants.PERMISSION.WORKSPACE_CREATE, response.data['role']['permissions'])

		# Load up the role separately and confirm.
		role = self.configuration.get_database_session().query(paasmaker.model.Role).get(role_id)
		self.assertIn(constants.PERMISSION.USER_CREATE, role.permissions)
		self.assertIn(constants.PERMISSION.WORKSPACE_CREATE, role.permissions)

	def test_edit_fail(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_CREATE])
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		role_id = response.data['role']['id']

		# Set up the request.
		request = paasmaker.common.api.role.RoleEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the role data from the server.
		request.load(role_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the role.
		request.set_role_name('')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("Invalid" in response.errors[0], "Missing message in error.")

	def test_list(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_CREATE])
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.role.RoleListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('roles'), "Missing roles list.")
		self.assertEquals(len(response.data['roles']), 1, "Not enough roles returned.")
		self.assertEquals(response.data['roles'][0]['name'], 'Test Role', "Returned role is not as expected.")

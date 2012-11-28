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

class RoleAllocationAssignSchema(colander.MappingSchema):
	role_id = colander.SchemaNode(colander.Integer(),
		title="Role ID",
		description="The role ID.")
	user_id = colander.SchemaNode(colander.Integer(),
		title="User ID",
		description="The user ID.")
	workspace_id = colander.SchemaNode(colander.Integer(),
		title="Optional Workspace ID",
		description="The workspace ID.",
		default=None,
		missing=None)

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
		roles = self.db().query(paasmaker.model.Role).all()
		self.add_data('roles', roles)

		self.render("role/list.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/list", RoleListController, configuration))
		return routes

class RoleAllocationListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		# TODO: Permissions.
		# TODO: Pagination.
		allocations = self.db().query(paasmaker.model.WorkspaceUserRole).all()
		self.add_data('allocations', allocations)

		self.render("role/allocationlist.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/allocation/list", RoleAllocationListController, configuration))
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
		paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)
		session.refresh(role)

		self.add_data('role', role)

		self.render("role/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/create", RoleEditController, configuration))
		routes.append((r"/role/(\d+)", RoleEditController, configuration))
		return routes

class RoleAllocationAssignController(BaseController):
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
		self.render("role/allocationassign.html")

	def post(self, role_id=None):
		# TODO: Permissions.
		if not self.validate_data(RoleAllocationAssignSchema()):
			return

		# Fetch the role, user, and workspace.
		role = self.db().query(paasmaker.model.Role).get(int(self.param('role_id')))
		user = self.db().query(paasmaker.model.User).get(int(self.param('user_id')))
		workspace_id = self.param('workspace_id')
		workspace = None
		if workspace_id:
			workspace = self.db().query(paasmaker.model.Workspace).get(workspace_id)

		if not role:
			self.add_error("No such role.")
		if not user:
			self.add_error("No such user.")
		if workspace_id and not workspace:
			self.add_error("No such workspace.")

		if len(self.errors) > 0:
			# TODO: A better error code...
			self.write_error(404)
		else:
			allocation = paasmaker.model.WorkspaceUserRole()
			allocation.user = user
			allocation.role = role
			allocation.workspace = workspace

			session = self.db()
			session.add(allocation)
			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)
			session.refresh(allocation)

			self.add_data('allocation', allocation)

		self.render("role/allocationassign.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/allocation/assign", RoleAllocationAssignController, configuration))
		return routes

class RoleEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = RoleEditController.get_routes({'configuration': self.configuration})
		routes.extend(RoleListController.get_routes({'configuration': self.configuration}))
		routes.extend(RoleAllocationListController.get_routes({'configuration': self.configuration}))
		routes.extend(RoleAllocationAssignController.get_routes({'configuration': self.configuration}))
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

	def test_list_allocation(self):
		session = self.configuration.get_database_session()
		user = paasmaker.model.User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.name = 'User Name'
		user.password = 'test'

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test Zone'

		role = paasmaker.model.Role()
		role.name = "Test"
		role.permissions = []

		session.add(user)
		session.add(workspace)
		session.add(role)
		session.commit()

		allocation = paasmaker.model.WorkspaceUserRole()
		allocation.user = user
		allocation.role = role
		session.add(allocation)

		other_allocation = paasmaker.model.WorkspaceUserRole()
		other_allocation.user = user
		other_allocation.role = role
		other_allocation.workspace = workspace
		session.add(other_allocation)
		session.commit()

		request = paasmaker.common.api.role.RoleAllocationListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('allocations'), "Missing allocations list.")
		self.assertEquals(len(response.data['allocations']), 2, "Not enough allocations returned.")
		self.assertEquals(response.data['allocations'][0]['user']['login'], 'username', "Returned allocations is not as expected.")

		# TODO: Test that the workspace is blank in one of the responses.

	def test_allocation(self):
		session = self.configuration.get_database_session()
		user = paasmaker.model.User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.name = 'User Name'
		user.password = 'test'

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test Zone'

		role = paasmaker.model.Role()
		role.name = "Test"
		role.permissions = []

		session.add(user)
		session.add(workspace)
		session.add(role)
		session.commit()
		session.refresh(user)
		session.refresh(workspace)
		session.refresh(role)

		request = paasmaker.common.api.role.RoleAllocationAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_allocation_params(user.id, role.id)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('allocation'), "Missing allocation.")
		self.assertEquals(response.data['allocation']['user']['id'], user.id, "User ID not as expected.")
		self.assertEquals(response.data['allocation']['role']['id'], role.id, "Role ID not as expected.")
		self.assertEquals(response.data['allocation']['workspace'], None, "Workspace is not None.")

		# Same again, but apply to a workspace.
		request = paasmaker.common.api.role.RoleAllocationAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_allocation_params(user.id, role.id, workspace.id)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('allocation'), "Missing allocation.")
		self.assertEquals(response.data['allocation']['user']['id'], user.id, "User ID not as expected.")
		self.assertEquals(response.data['allocation']['role']['id'], role.id, "Role ID not as expected.")
		self.assertEquals(response.data['allocation']['workspace']['id'], workspace.id, "Workspace is not None.")

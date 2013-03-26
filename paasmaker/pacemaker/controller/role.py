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

class RoleAllocationUnAssignSchema(colander.MappingSchema):
	allocation_id = colander.SchemaNode(colander.Integer(),
		title="Allocation ID",
		description="The allocation ID.")

class RoleListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.ROLE_LIST)
		roles = self.session.query(
			paasmaker.model.Role
		)
		
		self._paginate('roles', roles)
		# self.add_data('roles', roles)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/list", RoleListController, configuration))
		return routes

class RoleAllocationListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.ROLE_ASSIGN)
		allocations = self.session.query(
			paasmaker.model.WorkspaceUserRole
		).filter(
			paasmaker.model.WorkspaceUserRole.deleted == None
		)
		self._paginate('allocations', allocations)

		self.client_side_render()

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
			role = self.session.query(
				paasmaker.model.Role
			).get(int(role_id))
			if not role:
				raise HTTPError(404, "No such role.")

		return role

	def _default_role(self):
		role = paasmaker.model.Role()
		role.name = ''
		return role

	def get(self, role_id=None):
		self.require_permission(constants.PERMISSION.ROLE_EDIT)
		role = self._get_role(role_id)
		if not role:
			role = self._default_role()
		self.add_data('role', role)
		self.add_data_template('available_permissions', constants.PERMISSION.ALL)

		self.render("role/edit.html")

	def post(self, role_id=None):
		self.require_permission(constants.PERMISSION.ROLE_EDIT)
		role = self._get_role(role_id)

		valid_data = self.validate_data(RoleSchema())

		if not role:
			role = self._default_role()

		role.name = self.params['name']

		# And a special handler - if supplied with "ALL", replace with all
		# possible permissions.
		if 'ALL' in self.params['permissions']:
			role.permissions = constants.PERMISSION.ALL
		else:
			role.permissions = self.params['permissions']

		if valid_data:
			self.session.add(role)
			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(self.session)
			self.session.refresh(role)

			self.add_data('role', role)

			self.redirect('/role/list')
		else:
			self.add_data('role', role)
			self.add_data_template('available_permissions', constants.PERMISSION.ALL)
			self.render("role/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/create", RoleEditController, configuration))
		routes.append((r"/role/(\d+)", RoleEditController, configuration))
		return routes

class RoleAllocationAssignController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.ROLE_ASSIGN)
		# List available users, workspaces, and roles.
		# TODO: This won't be efficient at large sets.
		if self.format == 'html':
			# We don't expose this here to the API - this is
			# purely for the template to use.
			users = self.session.query(
				paasmaker.model.User
			).all()
			roles = self.session.query(
				paasmaker.model.Role
			).all()
			workspaces = self.session.query(
				paasmaker.model.Workspace
			).all()

			self.add_data_template('users', users)
			self.add_data_template('roles', roles)
			self.add_data_template('workspaces', workspaces)

		self.render("role/allocationassign.html")

	def post(self):
		self.require_permission(constants.PERMISSION.ROLE_ASSIGN)
		valid_data = self.validate_data(RoleAllocationAssignSchema())

		# Fetch the role, user, and workspace.
		role = self.session.query(
			paasmaker.model.Role
		).get(int(self.params['role_id']))
		user = self.session.query(
			paasmaker.model.User
		).get(int(self.params['user_id']))
		workspace_id = self.params['workspace_id']
		workspace = None
		if workspace_id:
			workspace = self.session.query(
				paasmaker.model.Workspace
			).get(int(workspace_id))

		if not role:
			self.add_error("No such role.")
			valid_data = False
		if not user:
			self.add_error("No such user.")
			valid_data = False
		if workspace_id and not workspace:
			self.add_error("No such workspace.")
			valid_data = False

		if valid_data:
			allocation = paasmaker.model.WorkspaceUserRole()
			allocation.user = user
			allocation.role = role
			allocation.workspace = workspace

			self.session.add(allocation)
			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(self.session)
			self.session.refresh(allocation)

			self.add_data('allocation', allocation)
			self.redirect('/role/allocation/list')
		else:
			self.render("role/allocationassign.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/allocation/assign", RoleAllocationAssignController, configuration))
		return routes

class RoleAllocationUnAssignController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def post(self):
		self.require_permission(constants.PERMISSION.ROLE_ASSIGN)
		valid_data = self.validate_data(RoleAllocationUnAssignSchema())

		# Fetch this allocation.
		allocation = self.session.query(
			paasmaker.model.WorkspaceUserRole
		).get(int(self.params['allocation_id']))

		if not allocation:
			raise tornado.HTTPError(404, "No such allocation.")

		allocation.delete()
		self.session.add(allocation)
		paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(self.session)

		self.add_data('success', True)

		self.redirect('/role/allocation/list')

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/role/allocation/unassign", RoleAllocationUnAssignController, configuration))
		return routes

class RoleEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = RoleEditController.get_routes({'configuration': self.configuration})
		routes.extend(RoleListController.get_routes({'configuration': self.configuration}))
		routes.extend(RoleAllocationListController.get_routes({'configuration': self.configuration}))
		routes.extend(RoleAllocationAssignController.get_routes({'configuration': self.configuration}))
		routes.extend(RoleAllocationUnAssignController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_EDIT])
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('role'), "Missing role object in return data.")
		self.assertTrue(response.data['role'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['role'].has_key('permissions'), "Missing permissions in return data.")
		self.assertIn(constants.PERMISSION.USER_EDIT, response.data['role']['permissions'])

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
		request.set_role_params('Test Role', [constants.PERMISSION.USER_EDIT])
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
		request.set_role_permissions(load_response['permissions'] + [constants.PERMISSION.WORKSPACE_EDIT])

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.data['role']['permissions']), 2, 'Not enough permissions.')
		self.assertIn(constants.PERMISSION.USER_EDIT, response.data['role']['permissions'])
		self.assertIn(constants.PERMISSION.WORKSPACE_EDIT, response.data['role']['permissions'])

		# Load up the role separately and confirm.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		role = session.query(
			paasmaker.model.Role
		).get(role_id)
		self.assertIn(constants.PERMISSION.USER_EDIT, role.permissions)
		self.assertIn(constants.PERMISSION.WORKSPACE_EDIT, role.permissions)

	def test_edit_fail(self):
		# Create the role.
		request = paasmaker.common.api.role.RoleCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_role_params('Test Role', [constants.PERMISSION.USER_EDIT])
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
		request.set_role_params('Test Role', [constants.PERMISSION.USER_EDIT])
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
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = paasmaker.model.User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.name = 'User Name'
		user.password = 'test'

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test Zone'
		workspace.stub = 'test'

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
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = paasmaker.model.User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.name = 'User Name'
		user.password = 'test'

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test Zone'
		workspace.stub = 'test'

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

		first_allocation_id = response.data['allocation']['id']

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

		second_allocation_id = response.data['allocation']['id']

		# Remove the allocations.
		request = paasmaker.common.api.role.RoleUnAllocationAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_allocation_id(first_allocation_id)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('success'), "Missing success flag.")

		# List it.
		request = paasmaker.common.api.role.RoleAllocationListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('allocations'), "Missing allocations list.")
		self.assertEquals(len(response.data['allocations']), 1, "Not enough allocations returned.")
		self.assertEquals(response.data['allocations'][0]['user']['login'], 'username', "Returned allocations is not as expected.")

		# Remove the other allocation.
		request = paasmaker.common.api.role.RoleUnAllocationAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_allocation_id(second_allocation_id)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('success'), "Missing success flag.")

		# List it. Should now be none.
		request = paasmaker.common.api.role.RoleAllocationListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('allocations'), "Missing allocations list.")
		self.assertEquals(len(response.data['allocations']), 0, "Not the right number of allocations.")
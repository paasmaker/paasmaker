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

class WorkspaceSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Workspace Name",
		description="The name of this workspace.",
		validator=colander.Length(min=2))
	# TODO: Put proper validation on this.
	stub = colander.SchemaNode(colander.String(),
		title="Workspace stub",
		description="A short, URL friendly name for the workspace.")
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Workspace Tags",
		description="A set of tags for this workspace.",
		missing={},
		default={})
	serialised_tags = colander.SchemaNode(colander.String(),
		title="Workspace Tags JSON",
		description="JSON-encoded version of the tags for this workspace; takes precedence over tags if set",
		missing="",
		default="")

class WorkspaceEditController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_workspace(self, workspace_id=None):
		workspace = None
		if workspace_id:
			# Find and load the workspace.
			workspace = self.session.query(
				paasmaker.model.Workspace
			).get(int(workspace_id))
			if not workspace:
				raise tornado.web.HTTPError(404, "No such workspace.")

			self.add_data('workspace', workspace)

		return workspace

	def _default_workspace(self):
		workspace = paasmaker.model.Workspace()
		workspace.name = ''
		return workspace

	def get(self, workspace_id=None):
		workspace = self._get_workspace(workspace_id)
		if not workspace:
			workspace = self._default_workspace()

		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)
		self.add_data('workspace', workspace)

		# Workaround for the fact that this controller is used for two things:
		# /workspace/1 in HTML format shows the edit page
		# /workspace/1?format=json is the API call for details about the workspace
		# The former requires WORKSPACE_EDIT and the latter only needs WORKSPACE_VIEW.
		# TODO: the former should probably be /workspace/1/edit
		if self.has_permission(constants.PERMISSION.WORKSPACE_EDIT):
			self.client_side_render()
		else:
			self.render("api/apionly.html")

	def post(self, workspace_id=None):
		workspace = self._get_workspace(workspace_id)
		self.require_permission(constants.PERMISSION.WORKSPACE_EDIT, workspace=workspace)

		valid_data = self.validate_data(WorkspaceSchema())

		if not workspace:
			workspace = self._default_workspace()

		workspace.name = self.params['name']
		workspace.tags = self.params['tags']
		workspace.stub = self.params['stub']

		if len(self.params['serialised_tags']) > 0:
			workspace.tags = json.loads(self.params['serialised_tags'])

		if valid_data:
			self.session.add(workspace)
			self.session.commit()
			self.session.refresh(workspace)

			self.add_data('workspace', workspace)

			self.action_success(None, '/workspace/' + str(workspace.id) + '/applications')

		else:
			self.add_data('workspace', workspace)
			self.render("workspace/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/create", WorkspaceEditController, configuration))
		routes.append((r"/workspace/(\d+)", WorkspaceEditController, configuration))
		return routes

class WorkspaceListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		# This helper fetches only the workspaces the logged in user
		# has permissions to access.
		workspaces = self._my_workspace_list()

		self._paginate('workspaces', workspaces)
		self.render("workspace/list.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/list", WorkspaceListController, configuration))
		return routes

class WorkspaceEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = WorkspaceEditController.get_routes({'configuration': self.configuration})
		routes.extend(WorkspaceListController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('workspace'), "Missing workspace object in return data.")
		self.assertTrue(response.data['workspace'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['workspace'].has_key('name'), "Missing name in return data.")

	def test_create_fail(self):
		# Send through some bogus data.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('a')
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('name'), "Missing error on name attribute.")

	def test_edit(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the workspace.
		request.set_workspace_name('Test Altered workspace')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(response.data['workspace']['name'], 'Test Altered workspace', 'Name was not updated.')
		# Load up the workspace separately and confirm.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		workspace = session.query(paasmaker.model.Workspace).get(workspace_id)
		self.assertEquals(workspace.name, 'Test Altered workspace', 'Name was not updated.')

	def test_edit_fail(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the workspace.
		request.set_workspace_name('a')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('name'), "Missing error on name attribute.")

	def test_list(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('workspaces'), "Missing workspaces list.")
		self.assertEquals(len(response.data['workspaces']), 1, "Not enough workspaces returned.")
		self.assertEquals(response.data['workspaces'][0]['name'], 'Test workspace', "Returned workspace is not as expected.")

		# Create a second workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Second Workspace')
		request.set_workspace_stub('test-two')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		second_workspace_id = int(response.data['workspace']['id'])

		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('workspaces'), "Missing workspaces list.")
		self.assertEquals(len(response.data['workspaces']), 2, "Not enough workspaces returned.")

		# Now, create a user and assign them permission only to view the second workspace.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = paasmaker.model.User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.password = 'testtest'
		role = paasmaker.model.Role()
		role.name = 'Workspace Level'
		role.add_permission(constants.PERMISSION.WORKSPACE_VIEW)

		session.add(user)
		session.add(role)

		workspace = session.query(paasmaker.model.Workspace).get(second_workspace_id)

		wu = paasmaker.model.WorkspaceUserRole()
		wu.workspace = workspace
		wu.user = user
		wu.role = role
		session.add(wu)
		session.commit()

		paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)

		session.refresh(user)

		# Fetch the workspace list as that user.
		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(self.configuration)
		request.set_auth(user.apikey)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('workspaces'), "Missing workspaces list.")
		self.assertEquals(len(response.data['workspaces']), 1, "Not enough workspaces returned.")
		self.assertEquals(response.data['workspaces'][0]['name'], 'Second Workspace', "Returned workspace is not as expected.")
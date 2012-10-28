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

class WorkspaceSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Workspace Name",
		description="The name of this workspace.",
		validator=colander.Length(min=2))
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Workspace Tags",
		description="A set of tags for this workspace.",
		missing={},
		default={})

class WorkspaceController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self, workspace_id):
		# TODO: Permissions.
		# Find and load the workspace.
		workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
		if not workspace:
			self.write_error(404, "No such workspace.")
		self.add_data('workspace', workspace)

		self.render("api/apionly.html")

	def post(self, workspace_id):
		self.get(workspace_id)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/(\d+)", WorkspaceController, configuration))
		return routes

class WorkspaceEditController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get_form(self, workspace=None):
		schema = WorkspaceSchema()
		if workspace:
			form = smallform.Form(schema, defaults=workspace.flatten())
		else:
			form = smallform.Form(schema)
		return form

	def get(self, workspace_id=None):
		# TODO: Permissions.
		workspace = None
		if workspace_id:
			# Find and load the workspace.
			workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
			if not workspace:
				self.write_error(404, "No such workspace.")
			self.add_data('workspace', workspace)

		form = self.get_form(workspace)
		form.validate(self.params)
		self.add_data_template('form', form)

		self.render("workspace/edit.html")

	def post(self, workspace_id=None):
		# TODO: Permissions.
		workspace = None
		if workspace_id:
			# Find and load the workspace.
			workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
			if not workspace:
				self.write_error(404, "No such workspace.")

		form = self.get_form(workspace)
		values = form.validate(self.params)
		if not form.errors:
			if not workspace_id:
				workspace = paasmaker.model.Workspace()
			workspace = form.bind(workspace)
			session = self.db()
			session.add(workspace)
			session.commit()
			session.refresh(workspace)

			self.add_data('workspace', workspace)

			self.redirect('/workspace/list')
			return
		else:
			for key, message in form.errors.iteritems():
				self.add_error("%s: %s" % (key, ", ".join(message)))

		self.add_data_template('form', form)

		self.render("workspace/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/create", WorkspaceEditController, configuration))
		routes.append((r"/workspace/edit/(\d+)", WorkspaceEditController, configuration))
		return routes

class WorkspaceListController(BaseController):
	auth_methods = [BaseController.NODE, BaseController.USER]

	def get(self):
		# TODO: Permissions.
		# TODO: Paginate...
		workspaces = self.db().query(paasmaker.model.Workspace)
		self.add_data('workspaces', workspaces)
		self.render("workspace/list.html")

	def post(self):
		self.get()

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
		routes.extend(WorkspaceController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_workspace_name('Test workspace')
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
		request.set_workspace_name('a')
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("Shorter" in response.errors[0], "Missing message in error.")

	def test_edit(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_workspace_name('Test workspace')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop)
		load_response = self.wait()
		self.failIf(not load_response.success)

		# Now attempt to change the workspace.
		request.set_workspace_name('Test Altered workspace')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(response.data['workspace']['name'], 'Test Altered workspace', 'Name was not updated.')
		# Load up the workspace separately and confirm.
		workspace = self.configuration.get_database_session().query(paasmaker.model.Workspace).get(workspace_id)
		self.assertEquals(workspace.name, 'Test Altered workspace', 'Name was not updated.')

	def test_edit_fail(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_workspace_name('Test workspace')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop)
		load_response = self.wait()
		self.failIf(not load_response.success)

		# Now attempt to change the workspace.
		request.set_workspace_name('a')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertTrue("name" in response.errors[0], "Missing message in error.")

	def test_list(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_workspace_name('Test workspace')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('workspaces'), "Missing workspaces list.")
		self.assertEquals(len(response.data['workspaces']), 1, "Not enough workspaces returned.")
		self.assertEquals(response.data['workspaces'][0]['name'], 'Test workspace', "Returned workspace is not as expected.")

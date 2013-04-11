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
import os
import tempfile
import re

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from user import UserEditController
from upload import UploadController
from workspace import WorkspaceEditController

from pubsub import pub
import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ApplicationNewSchema(colander.MappingSchema):
	scm = colander.SchemaNode(colander.String(),
		title="SCM Name",
		description="The SCM plugin name.")
	manifest_path = colander.SchemaNode(colander.String(),
		title="Manifest Path",
		description="The path to the manifest file inside the SCM.")
	uploaded_file = colander.SchemaNode(colander.String(),
		title="Uploaded File key",
		description="The uploaded file unique identifier. This is injected into the appropriate SCM at the right time if supplied.",
		default=None,
		missing=None,
		validator=colander.Regex(re.compile(r'^[A-Fa-f0-9]+$'), "Invalid uploaded file token."))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Parameters",
		description="Parameters for the target SCM. Validated when the plugin is called.",
		missing={},
		default={})

class ApplicationCurrentVersionSchema(colander.MappingSchema):
	version_id = colander.SchemaNode(colander.Integer(),
		title="Version ID",
		description="The application version ID to make current.")

class ApplicationRootController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_workspace(self, workspace_id):
		workspace = self.session.query(
			paasmaker.model.Workspace
		).get(int(workspace_id))

		if not workspace:
			raise tornado.web.HTTPError(404, "No such workspace.")
		if workspace.deleted:
			raise tornado.web.HTTPError(404, "Deleted workspace.")

		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)

		return workspace

	def _get_application(self, application_id):
		application = self.session.query(
			paasmaker.model.Application
		).get(int(application_id))

		if not application:
			raise tornado.web.HTTPError(404, "No such application.")
		if application.deleted:
			raise tornado.web.HTTPError(404, "Deleted application.")

		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=application.workspace)

		return application

class ApplicationListController(ApplicationRootController):

	def get(self, workspace_id):
		workspace = self._get_workspace(workspace_id)

		# TODO: Unit test.
		applications = self.session.query(
			paasmaker.model.Application
		).filter(
			paasmaker.model.Application.workspace == workspace
		).filter(
			paasmaker.model.Application.deleted == None
		)
		self.add_data('workspace', workspace)
		self._paginate('applications', applications)
		self.add_data_template('paasmaker', paasmaker)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/(\d+)/applications", ApplicationListController, configuration))
		return routes

# TODO: Unit test. Desperately required!
class ApplicationNewController(ApplicationRootController):

	def get(self, input_id):
		last_scm_name = None
		last_version_params = {}
		if self.request.uri.startswith('/application'):
			application = self._get_application(input_id)
			workspace = application.workspace
			self.add_data('new_application', False)
			self.add_data('application', application)

			# Get the last version, and thus it's last SCM parameters.
			last_version = self.session.query(
				paasmaker.model.ApplicationVersion
			).filter(
				paasmaker.model.ApplicationVersion.application == application
			).order_by(
				paasmaker.model.ApplicationVersion.version.desc()
			).first()

			# Make sure there was a last version.
			if last_version:
				self.add_data('last_version', last_version)
				last_version_params = last_version.scm_parameters
				last_scm_name = last_version.scm_name
		else:
			application = None
			workspace = self._get_workspace(input_id)
			self.add_data('new_application', True)
		self.add_data('workspace', workspace)
		self.add_data('last_scm_params', last_version_params)
		self.add_data('last_scm_name', last_scm_name)

		self.require_permission(constants.PERMISSION.APPLICATION_CREATE, workspace=workspace)

		# Return a list of available SCMs and stuff.
		scm_plugins = self.configuration.plugins.plugins_for(paasmaker.util.plugin.MODE.SCM_FORM)

		result_list = []
		repo_lister_master = self.configuration['pacemaker']['scmlisters']
		for plugin_name in scm_plugins:
			plugin = self.configuration.plugins.instantiate(
				plugin_name,
				paasmaker.util.plugin.MODE.SCM_FORM
			)

			# Get a list of listers as well.
			repo_listers = []
			for lister in repo_lister_master:
				if lister['for'] == plugin_name:
					for repo_plugin in lister['plugins']:
						lister_meta = {}
						lister_meta['plugin'] = repo_plugin
						lister_meta['title'] = self.configuration.plugins.title(repo_plugin)
						repo_listers.append(lister_meta)

			result = {}
			result['listers'] = repo_listers

			if self.format == 'html':
				# Fetch the HTML instead.
				result['plugin'] = plugin_name
				result['title'] = self.configuration.plugins.title(plugin_name)
				result['form'] = plugin.create_form(last_version_params)
			else:
				result['plugin'] = plugin_name
				result['title'] = self.configuration.plugins.title(plugin_name)
				result['parameters'] = plugin.create_summary()
				result['parameters']['manifest_path'] = "The path inside the SCM to the manifest file."

			result_list.append(result)

		self.add_data('scms', result_list)

		# Special case for this controller: because SCM plugins generate their own form and return an
		# HTML string, this controller supports a ?raw=true suffix on the URL to return the contents
		# of the template rendered without any chrome from main.html. This can then be injected into
		# the page by JavaScript. Without the suffix, treat as a normal client_side_render().
		# TODO: a better method for SCM plugins to define their inputs
		if self.get_argument('raw', '') == 'true':
			self.render("application/new.html")
		else:
			self.client_side_render()

	def post(self, input_id):
		if self.request.uri.startswith('/application'):
			application = self._get_application(input_id)
			application_id = application.id
			application_name = application.name
			workspace = application.workspace
			self.add_data('new_application', False)
			self.add_data('application', application)
		else:
			application = None
			application_id = None
			application_name = 'New Application'
			workspace = self._get_workspace(input_id)
			self.add_data('new_application', True)

		self.add_data('workspace', workspace)

		self.require_permission(constants.PERMISSION.APPLICATION_CREATE, workspace=workspace)

		# Check parameters.
		valid_data = self.validate_data(ApplicationNewSchema())
		if not valid_data:
			# TODO: This is a catch for HTML requests.
			# Supply back a much nicer error, and probably refill forms and stuff.
			raise tornado.web.HTTPError(400, "Invalid parameters")

		raw_scm_parameters = self.params['parameters']
		upload_location = None
		if self.params['uploaded_file']:
			# Insert the location of the file into the raw SCM params.
			# NOTE: This parameter is checked by a regex in the colander
			# schema to only allow [A-Fa-f0-9]+. This prevents users from
			# inserting their own local filesystem path...
			upload_location = os.path.join(
				self.configuration.get_scratch_path_exists('uploads'),
				self.params['uploaded_file']
			)
			raw_scm_parameters['location'] = upload_location

		def job_started():
			if application:
				self.action_success(self.get_data('job_id'), '/application/%d' % application.id)
			else:
				self.action_success(self.get_data('job_id'), '/workspace/%d/applications' % workspace.id)

		def application_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		paasmaker.common.job.prepare.prepareroot.ApplicationPrepareRootJob.setup(
			self.configuration,
			application_name,
			self.params['manifest_path'],
			workspace.id,
			self.params['scm'],
			raw_scm_parameters,
			application_job_ready,
			application_id=application_id
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/(\d+)/applications/new", ApplicationNewController, configuration))
		routes.append((r"/application/(\d+)/newversion", ApplicationNewController, configuration))
		return routes

class ApplicationController(ApplicationRootController):

	def get(self, application_id):
		application = self._get_application(application_id)

		# TODO: Unit test.
		self.add_data('application', application)

		count = {}
		for version in application.versions:
			count[version.id] = 0;
			for type in version.instance_types:
				count[version.id] = count[version.id] + type.instances.count()
		self.add_data('instance_counts', count)

		workspace = self._get_workspace(application.workspace_id)
		self.add_data('workspace', workspace)
		self.add_data_template('paasmaker', paasmaker)

		applications = self.session.query(
			paasmaker.model.Application
		).filter(
			paasmaker.model.Application.workspace == workspace
		).filter(
			paasmaker.model.Application.deleted == None
		)
		self.add_data('applications', applications)

		versions = application.versions.filter(
			paasmaker.model.ApplicationVersion.deleted == None
		).order_by(
			paasmaker.model.ApplicationVersion.version.desc()
		)

		current_version = application.versions.filter(
			paasmaker.model.ApplicationVersion.is_current == True
		).first()

		self._paginate('versions', versions)
		self.add_data_template('constants', constants)
		self.add_data('current_version', current_version)
		self.add_data('page', 'application')

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)", ApplicationController, configuration))
		return routes

class ApplicationSetCurrentController(ApplicationRootController):

	def post(self, input_id):
		if self.request.uri.startswith('/application'):
			application = self._get_application(input_id)
			valid_data = self.validate_data(ApplicationCurrentVersionSchema())
			if not valid_data:
				# Nope. No recourse here.
				raise tornado.web.HTTPError(400, "Invalid data supplied.")
			# Load up the version.
			version = self.session.query(paasmaker.model.ApplicationVersion).get(int(self.params['version_id']))
		else:
			version = self.session.query(paasmaker.model.ApplicationVersion).get(int(input_id))
			if not version:
				raise tornado.web.HTTPError(404, "No such version.")
			application = version.application

		# Check permissions.
		self.require_permission(constants.PERMISSION.APPLICATION_ROUTING, workspace=application.workspace)

		# Check that the version is part of this application.
		if version.application_id != application.id:
			raise tornado.web.HTTPError(404, "Requested version is not part of the requested application.")

		if version.state != constants.VERSION.RUNNING:
			self.add_error("Version must be in state RUNNING to be current.")
			raise tornado.web.HTTPError(400, "Incorrect state.")

		# TODO: Unit test.
		def job_started():
			self.action_success(self.get_data('job_id'), "/application/%d" % application.id)

		def current_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		paasmaker.common.job.coordinate.current.CurrentVersionRequestJob.setup_version(
			self.configuration,
			version.id,
			current_job_ready,
			self._database_session_error
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)/setcurrent", ApplicationSetCurrentController, configuration))
		routes.append((r"/version/(\d+)/setcurrent", ApplicationSetCurrentController, configuration))
		return routes


class ApplicationDeleteController(ApplicationRootController):

	def post(self, input_id):
		application = self._get_application(input_id)

		self.require_permission(constants.PERMISSION.APPLICATION_DELETE, workspace=application.workspace)

		if not application.can_delete:
			raise tornado.web.HTTPError(400, "Cannot delete application that is still active")

		def job_started():
			# Redirect to clear the post.
			self._redirect_job(self.get_data('job_id'), '/workspace/%d/applications' % application.workspace.id)

		def delete_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		paasmaker.common.job.delete.application.ApplicationDeleteRootJob.setup_for_application(
			self.configuration,
			application,
			delete_job_ready
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)/delete", ApplicationDeleteController, configuration))
		return routes


class ApplicationServiceListController(ApplicationRootController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self, application_id):
		application = self._get_application(application_id)
		self.require_permission(constants.PERMISSION.SERVICE_VIEW, workspace=application.workspace)

		self.add_data('services', application.services)

		exportable_services = {}
		if self.has_permission(constants.PERMISSION.SERVICE_EXPORT, workspace=application.workspace):
			services = self.configuration.plugins.plugins_for(paasmaker.util.plugin.MODE.SERVICE_EXPORT)
			for plugin in services:
				exportable_services[plugin] = True
		self.add_data('exportable_services', exportable_services)
		importable_services = {}
		if self.has_permission(constants.PERMISSION.SERVICE_IMPORT, workspace=application.workspace):
			services = self.configuration.plugins.plugins_for(paasmaker.util.plugin.MODE.SERVICE_IMPORT)
			for plugin in services:
				importable_services[plugin] = True
		self.add_data('importable_services', importable_services)

		# self.add_data('application', application)
		# self.add_data_template('json', json)

		# TODO: we only need version ID and name here, and the API would probably be cleaner
		# if it was just a list of IDs. Maybe write an alternative to add_extra_data_fields?
		self.add_extra_data_fields(paasmaker.model.Service, 'application_versions')

		if self.has_permission(constants.PERMISSION.SERVICE_CREDENTIAL_VIEW, workspace=application.workspace):
			self.add_extra_data_fields(paasmaker.model.Service, 'credentials')

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)/services", ApplicationServiceListController, configuration))
		return routes

class ApplicationControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def setUp(self):
		super(ApplicationControllerTest, self).setUp()
		# Start the job manager (since application creation is a job)
		self.manager = self.configuration.job_manager
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ApplicationDeleteController.get_routes({'configuration': self.configuration})
		routes.extend(ApplicationNewController.get_routes({'configuration': self.configuration}))
		routes.extend(ApplicationListController.get_routes({'configuration': self.configuration}))
		routes.extend(UploadController.get_routes({'configuration': self.configuration}))
		routes.extend(UserEditController.get_routes({'configuration': self.configuration}))
		routes.extend(WorkspaceEditController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_application_create_and_delete(self):
		# Create a user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		# Fetch that user from the db.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = session.query(paasmaker.model.User).get(response.data['user']['id'])
		apikey = user.apikey

		# And give them permission to upload a file.
		# TODO: Check permissions work as well.
		role = paasmaker.model.Role()
		role.name = "Upload"
		role.permissions = constants.PERMISSION.ALL
		session.add(role)
		allocation = paasmaker.model.WorkspaceUserRole()
		allocation.user = user
		allocation.role = role
		session.add(allocation)
		paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)

		# Create a tar file of the sample tornado app
		tarfile = self.pack_sample_application("tornado-simple")

		def progress_callback(position, total):
			logger.info("Progress: %d of %d bytes uploaded.", position, total)

		# Now, attempt to upload a file.
		request = paasmaker.common.api.upload.UploadFileAPIRequest(self.configuration)
		request.set_auth(apikey)
		request.send_file(tarfile, progress_callback, self.stop, self.stop)
		result = self.wait()

		# Check that it succeeded.
		self.assertTrue(result['data']['success'], "Uploading application file didn't succeed")
		remote_file_id = result['data']['identifier']

		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_auth(apikey)
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()
		new_workspace_id =  response.data['workspace']['id']

		# The tar-unpacking SCM isn't enabled by default
		self.configuration.plugins.register(
			'paasmaker.scm.tarball',
			'paasmaker.pacemaker.scm.tarball.TarballSCM',
			{},
			'Tarball SCM'
		)

		# First try creating a new application with our tarball
		request = paasmaker.common.api.application.ApplicationNewAPIRequest(self.configuration)
		request.set_workspace(new_workspace_id)
		request.set_auth(apikey)
		request.set_scm("paasmaker.scm.tarball")
		request.set_uploaded_file(remote_file_id)
		request.send(self.stop)
		response = self.wait()

		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		self.assertTrue(response.data['new_application'], "Sending ApplicationNewAPIRequest didn't create a new application")

		result = self.wait()
		while result.state not in (constants.JOB_FINISHED_STATES):
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Application creation job did not succeed")

		# List applications in this workspace, to get the app ID
		request = paasmaker.common.api.application.ApplicationListAPIRequest(self.configuration)
		request.set_workspace(new_workspace_id)
		request.set_auth(apikey)
		request.send(self.stop)
		response = self.wait()

		self.assertEquals(len(response.data['applications']), 1, "ApplicationListAPIRequest returned %d results, but we only created one." % len(response.data['applications']))
		application_id = response.data['applications'][0]['id']

		# Now use the same tarball to create a new version
		request = paasmaker.common.api.application.ApplicationNewVersionAPIRequest(self.configuration)
		request.set_application(application_id)
		request.set_auth(apikey)
		request.set_scm("paasmaker.scm.tarball")
		request.set_uploaded_file(remote_file_id)
		request.send(self.stop)
		response = self.wait()

		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		self.assertFalse(response.data['new_application'], "Sending ApplicationNewVersionAPIRequest created a new application rather than a new version")

		result = self.wait()
		while result.state not in (constants.JOB_FINISHED_STATES):
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "New application version job did not succeed")

		# Now delete the new application!
		request = paasmaker.common.api.application.ApplicationDeleteAPIRequest(self.configuration)
		request.set_application(application_id)
		request.set_auth(apikey)
		request.send(self.stop)
		response = self.wait()

		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		result = self.wait()
		while result.state not in (constants.JOB_FINISHED_STATES):
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Application delete job did not succeed")

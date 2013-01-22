import unittest
import uuid
import logging
import json
import os
import tempfile

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

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
		missing=None)
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Paramters",
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
		workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
		if not workspace:
			raise tornado.web.HTTPError(404, "No such workspace.")
		if workspace.deleted:
			raise tornado.web.HTTPError(404, "Deleted workspace.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)
		return workspace

	def _get_application(self, application_id):
		application = self.db().query(paasmaker.model.Application).get(int(application_id))
		if not application:
			raise tornado.web.HTTPError(404, "No such application.")
		if application.deleted:
			raise tornado.web.HTTPError(404, "Deleted application.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=application.workspace)
		return application

class ApplicationListController(ApplicationRootController):

	@tornado.web.asynchronous
	def get(self, workspace_id):
		workspace = self._get_workspace(workspace_id)

		# TODO: Unit test.
		applications = self.db().query(
			paasmaker.model.Application
		).filter(
			paasmaker.model.Application.workspace == workspace
		).filter(
			paasmaker.model.Application.deleted == None
		)
		self.add_data('workspace', workspace)
		self._paginate('applications', applications)
		self.add_data_template('paasmaker', paasmaker)

		# Fetch the router stats.
		self._get_router_stats_for('workspace', workspace.id, self._got_stats)

	def _got_stats(self, result):
		self.render("application/list.html")

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
			last_version = self.db().query(
				paasmaker.model.ApplicationVersion
			).filter(
				paasmaker.model.ApplicationVersion.application == application
			).order_by(
				paasmaker.model.ApplicationVersion.version.desc()
			).first()

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
		self.render("application/new.html")

	@tornado.web.asynchronous
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
			upload_location = os.path.join(
				self.configuration.get_scratch_path_exists('uploads'),
				self.params['uploaded_file']
			)
			raw_scm_parameters['location'] = upload_location

		def job_started():
			self._redirect_job(self.get_data('job_id'), '/workspace/%d/applications' % workspace.id)

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

	@tornado.web.asynchronous
	def get(self, application_id):
		application = self._get_application(application_id)

		# TODO: Unit test.
		self.add_data('application', application)

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

		# Fetch the router stats.
		self._get_router_stats_for('application', application.id, self._got_stats)

	def _got_stats(self, result):
		self.render("application/versions.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)", ApplicationController, configuration))
		return routes

class ApplicationSetCurrentController(ApplicationRootController):

	@tornado.web.asynchronous
	def post(self, input_id):
		if self.request.uri.startswith('/application'):
			application = self._get_application(input_id)
			valid_data = self.validate_data(ApplicationCurrentVersionSchema())
			if not valid_data:
				# Nope. No recourse here.
				raise tornado.web.HTTPError(400, "Invalid data supplied.")
			# Load up the version.
			version = self.db().query(paasmaker.model.ApplicationVersion).get(int(self.params['version_id']))
		else:
			version = self.db().query(paasmaker.model.ApplicationVersion).get(int(input_id))
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
			# Redirect to clear the post.
			self._redirect_job(self.get_data('job_id'), '/application/%d' % application.id)

		def current_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		paasmaker.common.job.coordinate.current.CurrentVersionRequestJob.setup_version(
			self.configuration,
			version.id,
			current_job_ready
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)/setcurrent", ApplicationSetCurrentController, configuration))
		routes.append((r"/version/(\d+)/setcurrent", ApplicationSetCurrentController, configuration))
		return routes


class ApplicationDeleteController(ApplicationRootController):

	@tornado.web.asynchronous
	def post(self, input_id):
		application = self._get_application(input_id)

		self.require_permission(constants.PERMISSION.APPLICATION_DELETE, workspace=application.workspace)

		session = self.db()
		if not application.can_delete():
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
		self.require_permission(constants.PERMISSION.APPLICATION_SERVICE_DETAIL, workspace=application.workspace)

		self._paginate('services', application.services)
		self.add_data_template('json', json)

		self.render("application/services.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/application/(\d+)/services", ApplicationServiceListController, configuration))
		return routes
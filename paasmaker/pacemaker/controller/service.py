#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import datetime
import tempfile
import os
import re

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from ..service.base import BaseService
from user import UserEditController
from upload import UploadController
from workspace import WorkspaceEditController

import tornado
import colander
from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ServiceExportSchema(colander.MappingSchema):
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Parameters",
		description="Parameters for the service exporter, if required.",
		missing={},
		default={})

class ServiceExportController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	# We allow GET and POST methods, to allow fetching
	# with no parameters, or with parameters.

	def get(self, service_id):
		self.post(service_id)

	def post(self, service_id):
		# Load the service record from the database.
		service = self.session.query(
			paasmaker.model.Service
		).get(int(service_id))

		if service is None:
			raise tornado.web.HTTPError(404, "No such service.")

		# Check permissions.
		self.require_permission(
			constants.PERMISSION.SERVICE_EXPORT,
			workspace=service.application.workspace
		)

		# Now see if the service can be exported.
		can_export = self.configuration.plugins.exists(
			service.provider,
			paasmaker.util.plugin.MODE.SERVICE_EXPORT
		)

		if not can_export:
			raise tornado.web.HTTPError(400, "This service can not be exported.")

		if service.state != constants.SERVICE.AVAILABLE:
			raise tornado.web.HTTPError(400, "Can not export a service that is not available.")

		self.validate_data(ServiceExportSchema())

		# Tell the upstream Nginx to not buffer this request.
		# http://wiki.nginx.org/X-accel#X-Accel-Buffering
		self.set_header('X-Accel-Buffering', 'no')
		self.set_header('Content-Type', 'application/octet-stream')

		# Instantiate the plugin, and export it, streaming back the data.
		# TODO: Catch errors in the parameters.
		self.plugin = self.configuration.plugins.instantiate(
			service.provider,
			paasmaker.util.plugin.MODE.SERVICE_EXPORT,
			self.params['parameters']
		)

		# Get the plugin to suggest a filename.
		filename = self.plugin.export_filename(service)
		self.set_header('Content-Disposition', 'attachment; filename=%s' % filename)
		self.first_data = True

		self.export_in_progress = True
		self.plugin.export(
			service.name,
			service.credentials,
			self._complete,
			self._error,
			self._stream
		)

	def _complete(self, message):
		# Finished. Finish the request.
		self.export_in_progress = False
		logger.info(message)
		self.finish()

	def _error(self, message, exception=None):
		self.export_in_progress = False
		logger.error(message)
		if exception:
			logger.error("Exception:", exc_info=exception)
		self.add_error(message)
		self.add_error(str(ex))

		self.render("api/apionly.html")

	def _stream(self, data):
		if self.first_data:
			# Send an extra header that indicates that we've started successfully.
			# Why do we do this? On the client side, we need to know if the data coming in the
			# body is an error or actual data.
			self.set_header('X-Paasmaker-Service-Export-Success', 'true')
			self.first_data = False

		# Send the stream back to the client.
		self.write(data)
		# And flush now, because we want to stream it back.
		self.flush()

	def on_finished(self):
		# Cancel an in-progress export.
		if hasattr(self, 'export_in_progress') and self.export_in_progress:
			self.plugin.export_cancel()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/service/export/(\d+)", ServiceExportController, configuration))
		return routes

class ServiceImportSchema(colander.MappingSchema):
	uploaded_file = colander.SchemaNode(colander.String(),
		title="Uploaded File key",
		description="The uploaded file unique identifier.",
		default=None,
		missing=None,
		validator=colander.Regex(re.compile(r'^[A-Fa-f0-9]+$'), "Invalid uploaded file token."))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Parameters",
		description="Parameters for the target SCM. Validated when the plugin is called.",
		missing={},
		default={})

class ServiceImportController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def post(self, service_id):
		# Load the service record from the database.
		service = self.session.query(
			paasmaker.model.Service
		).get(int(service_id))

		if service is None:
			raise tornado.web.HTTPError(404, "No such service.")

		# Check permissions.
		self.require_permission(
			constants.PERMISSION.SERVICE_IMPORT,
			workspace=service.application.workspace
		)

		# Now see if the service can be exported.
		can_import = self.configuration.plugins.exists(
			service.provider,
			paasmaker.util.plugin.MODE.SERVICE_IMPORT
		)

		if not can_import:
			raise tornado.web.HTTPError(400, "This service can not be imported.")

		if service.state != constants.SERVICE.AVAILABLE:
			raise tornado.web.HTTPError(400, "Can not import a service that is not available.")

		self.validate_data(ServiceImportSchema())

		def job_started():
			# Redirect to clear the post.
			self._redirect_job(self.get_data('job_id'), '/application/%d' % service.application.id)

		def import_job_ready(job_id):
			self.add_data('job_id', job_id)
			self.configuration.job_manager.allow_execution(job_id, callback=job_started)

		# NOTE: This parameter is checked by a regex in the colander
		# schema to only allow [A-Fa-f0-9]+. This prevents users from
		# inserting their own local filesystem path...
		filename = os.path.join(
			self.configuration.get_scratch_path_exists('uploads'),
			self.params['uploaded_file']
		)

		paasmaker.common.job.service.serviceimport.ServiceImportJob.setup_for_service(
			self.configuration,
			service,
			filename,
			import_job_ready,
			delete_after_import=True
		)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/service/import/(\d+)", ServiceImportController, configuration))
		return routes

class DummyImportExportServiceOptionsSchema(colander.MappingSchema):
	pass

class DummyImportExportService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_EXPORT: DummyImportExportServiceOptionsSchema(),
		paasmaker.util.plugin.MODE.SERVICE_IMPORT: DummyImportExportServiceOptionsSchema()
	}
	OPTIONS_SCHEMA = DummyImportExportServiceOptionsSchema()
	API_VERSION = "0.9.0"

	def export(self, name, credentials, complete_callback, error_callback, stream_callback):
		self.blocks = 10
		self.complete_callback = complete_callback
		self.error_callback = error_callback
		self.stream_callback = stream_callback

		self.configuration.io_loop.add_callback(self._send_block)

	def _send_block(self):
		self.blocks -= 1
		self.stream_callback("test" * 2000)

		if self.blocks < 1:
			self.configuration.io_loop.add_callback(self._finish)
		else:
			self.configuration.io_loop.add_callback(self._send_block)

	def _finish(self):
		self.complete_callback("Completed exporting.")

	def export_filename(self, service):
		filename = super(DummyImportExportService, self).export_filename(service)
		return filename + ".test"

	def import_file(self, name, credentials, filename, callback, error_callback):
		# Read the file and return that in the callback.
		def read_file():
			contents = open(filename, 'r').read()
			callback(contents)

		self.configuration.io_loop.add_callback(read_file)

class ServiceExportImportControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def setUp(self):
		super(ServiceExportImportControllerTest, self).setUp()

		# Register a dummy service plugin.
		self.configuration.plugins.register(
			'paasmaker.service.dummyexportimport',
			'paasmaker.pacemaker.controller.service.DummyImportExportService',
			{},
			'Dummy export/import service'
		)

		# Start the job manager.
		self.manager = self.configuration.job_manager
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ServiceExportController.get_routes({'configuration': self.configuration})
		routes.extend(ServiceImportController.get_routes({'configuration': self.configuration}))
		routes.extend(UploadController.get_routes({'configuration': self.configuration}))
		routes.extend(UserEditController.get_routes({'configuration': self.configuration}))
		routes.extend(WorkspaceEditController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_export(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		# Create the service record in the database.
		workspace = paasmaker.model.Workspace()
		workspace.name = "Test"
		workspace.stub = "test"

		application = paasmaker.model.Application()
		application.name = "test"
		application.workspace = workspace

		service = paasmaker.model.Service()
		service.name = "testexport"
		service.credentials = {}
		service.provider = 'paasmaker.service.dummyexportimport'
		service.parameters = {}
		service.application = application
		service.state = constants.SERVICE.AVAILABLE

		session.add(service)
		session.commit()

		session.refresh(service)

		# Now attempt to fetch this service.
		request = paasmaker.common.api.service.ServiceExportAPIRequest(self.configuration)
		request.set_superkey_auth()

		request.set_service_id(service.id)

		def progress(position):
			logger.info("Got %d bytes", position)

		def success(message):
			self.stop(message)

		def error(message):
			self.stop(message)

		output_location = tempfile.mkstemp()[1]

		request.fetch(success, error, progress_callback=progress, output_file=output_location)
		result = self.wait()
		self.assertIn('Successfully', result, "Did not succeed.")

		contents = open(output_location, 'r').read()

		self.assertIn('test', contents, "Contents did not contain expected output.")
		self.assertEquals(os.path.getsize(output_location), 80000, "File was not expected %d bytes (was %d)." % (80000, os.path.getsize(output_location)))

		# Test the error scenario.
		# In this case, use a service that doesn't exist.
		service.provider = "paasmaker.service.dummynoexist"
		session.add(service)
		session.commit()

		request.fetch(success, error, progress_callback=progress, output_file=output_location)
		result = self.wait()
		self.assertIn('can not be exported', result, "Did not fail.")

		if os.path.exists(output_location):
			os.unlink(output_location)

	def test_import(self):
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

		testfile = tempfile.mkstemp()[1]
		fp = open(testfile, 'w')
		fp.write("test contents of import")
		fp.close()

		def progress_callback(position, total):
			logger.info("Progress: %d of %d bytes uploaded.", position, total)

		# Now, attempt to upload a file.
		request = paasmaker.common.api.upload.UploadFileAPIRequest(self.configuration)
		request.set_auth(apikey)
		request.send_file(testfile, progress_callback, self.stop, self.stop)
		result = self.wait()

		# Check that it succeeded.
		self.assertTrue(result['data']['success'], "Uploading test file didn't succeed")
		remote_file_id = result['data']['identifier']

		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_auth(apikey)
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()
		new_workspace_id =  response.data['workspace']['id']

		# Fetch a database session.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		# Create a dummy application and service.
		workspace = session.query(
			paasmaker.model.Workspace
		).get(new_workspace_id)

		application = paasmaker.model.Application()
		application.name = "test"
		application.workspace = workspace

		service = paasmaker.model.Service()
		service.name = "testexport"
		service.credentials = {}
		service.provider = 'paasmaker.service.dummyexportimport'
		service.parameters = {}
		service.application = application
		service.state = constants.SERVICE.AVAILABLE

		session.add(service)
		session.commit()

		session.refresh(service)

		# Now attempt to import it.
		request = paasmaker.common.api.service.ServiceImportAPIRequest(self.configuration)
		request.set_service(service.id)
		request.set_auth(apikey)
		request.set_uploaded_file(remote_file_id)
		request.send(self.stop)
		response = self.wait()

		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		# Wait for the import to finish successfully.
		result = self.wait()
		while result.state not in (constants.JOB_FINISHED_STATES):
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Service import job did not succeed.")
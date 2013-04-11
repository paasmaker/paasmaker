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

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from ..service.base import BaseService

import tornado
import colander

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

class DummyExportableServiceOptionsSchema(colander.MappingSchema):
	# No parameters required. Plugins just ask for a database.
	pass

class DummyExportableService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_EXPORT: DummyExportableServiceOptionsSchema()
	}
	OPTIONS_SCHEMA = DummyExportableServiceOptionsSchema()
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
		filename = super(DummyExportableService, self).export_filename(service)
		return filename + ".test"

class ServiceExportControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def setUp(self):
		super(ServiceExportControllerTest, self).setUp()

		# Register a dummy service plugin.
		self.configuration.plugins.register(
			'paasmaker.service.dummyexport',
			'paasmaker.pacemaker.controller.service.DummyExportableService',
			{},
			'Dummy export service'
		)

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = ServiceExportController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
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
		service.provider = 'paasmaker.service.dummyexport'
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

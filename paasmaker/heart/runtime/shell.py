
import subprocess
import os
import signal
import re
import uuid
import tempfile
import time

import paasmaker
from base import BaseRuntime, BaseRuntimeTest

import colander
import tornado

class ShellRuntimeOptionsSchema(colander.MappingSchema):
	# No options.
	pass

class ShellRuntimeParametersSchema(colander.MappingSchema):
	launch_command = colander.SchemaNode(colander.String(),
		title="Launch command",
		description="The command to launch the instance. Substitutes %(port)d with the allocated port.")
	start_timeout = colander.SchemaNode(colander.Integer(),
		title="Startup timeout",
		description="The maximum time to wait for the application to start listening on it's assigned port.",
		missing=60,
		default=60)

class ShellEnvironmentParametersSchema(colander.MappingSchema):
	# No options.
	pass

class ShellRuntime(BaseRuntime):
	MODES = {
		paasmaker.util.plugin.MODE.RUNTIME_EXECUTE: ShellRuntimeParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT: ShellEnvironmentParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS: None
	}
	OPTIONS_SCHEMA = ShellRuntimeOptionsSchema()

	def get_versions(self):
		# Just return this version.
		return ['1']

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def start(self, version, instance_id, callback, error_callback):
		# Prepare the launch command.
		instance = self.configuration.instances.get_instance(instance_id)
		launch_params = {}
		launch_params['port'] = instance['instance']['port']
		launch_command = self.parameters['launch_command'] % launch_params

		# Launch it.
		self.supervise_start(
			instance_id,
			launch_command,
			instance['runtime']['path'],
			instance['environment']
		)

		# If it's not standalone, wait for it to assume it's TCP port.
		if not instance['instance_type']['standalone']:
			# TODO: Handle the case where the instance id gets a stop signal
			# because the subprocess terminated.
			def abort_result(message):
				error_callback("Failed to start up instance inside timeout.")

			def abort_startup(message):
				# Failed to start up in time. Stop the instance.
				self.stop(instance_id, abort_result, abort_result)

			self.wait_until_port_used(
				instance['instance']['port'],
				self.parameters['start_timeout'],
				callback,
				abort_startup
			)
		else:
			# Assume that it's running, until the instance tells
			# us otherwise.
			callback("Started successfully.")

	def stop(self, version, instance_id, callback, error_callback):
		# Issue the stop command.
		try:
			self.supervise_stop(instance_id)
		except OSError, ex:
			# Probably no such PID. Failed!
			error_callback(str(ex), ex)
			return

		# Wait for it to free up the port, if it's not standalone.
		# If it's not standalone, wait for it to assume it's TCP port.
		instance = self.configuration.instances.get_instance(instance_id)
		if not instance['instance_type']['standalone']:
			def timeout(message):
				# Failed to stop listening, so it's not responding.
				error_callback(message)

			self.wait_until_port_free(
				instance['instance']['port'],
				self.parameters['start_timeout'],
				callback,
				timeout
			)
		else:
			# Assume that it's stopped.
			callback("Started successfully.")

	def status(self, version, instance_id, callback, error_callback):
		if self.supervise_is_running(instance_id):
			callback("Instance is running.")
		else:
			error_callback("Instance is not running.", exception=None)

	def statistics(self, instance_id, callback, error_callback):
		raise NotImplementedError("You must implement statistics.")

class ShellRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(ShellRuntimeTest, self).setUp()

	def tearDown(self):
		super(ShellRuntimeTest, self).tearDown()

	def test_options(self):
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {}, 'Shell Runtime')
		instance = self.configuration.plugins.instantiate('paasmaker.runtime.shell', paasmaker.util.plugin.MODE.RUNTIME_EXECUTE, {'launch_command': 'test.py'})
		self.assertTrue(True, "Should have got here...")

	def test_versions(self):
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {}, 'Shell Runtime')
		instance = self.configuration.plugins.instantiate('paasmaker.runtime.shell', paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)

		versions = instance.get_versions()

		self.assertEquals(len(versions), 1, "More than one version?")
		self.assertEquals(versions[0], "1", "Wrong version returned.")

	def test_startup(self):
		# Put together the barest of possible information to start up the system.
		instance_id = str(uuid.uuid4())
		instance = {}
		instance['instance'] = {'instance_id': instance_id}
		instance['instance']['port'] = self.configuration.get_free_port()
		instance['instance_type'] = {'standalone': False}
		start_environment = {'PM_METADATA': '{}'}
		instance['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(self.configuration, start_environment)

		# Register the instance, and then configure the runtime parameters.
		self.configuration.instances.add_instance(instance_id, instance)
		instance['runtime']['path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')

		# Now add the plugin, and instantiate.
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {}, 'Shell Runtime')
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{'launch_command': 'python app.py --port=%(port)d'}
		)

		# Should not be running.
		runtime.status(
			'1',
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success)

		# Start it up.
		runtime.start(
			'1',
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
		self.wait()
		self.assertTrue(self.success)

		# It should be running if we ask.
		runtime.status(
			'1',
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertTrue(self.success)

		# For debugging, print out the log.
		log_path = self.configuration.get_job_log_path(instance_id)
		#print open(log_path, 'r').read()

		# And see if it's really working.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		#print open(log_path, 'r').read()

		self.failIf(response.error)
		self.assertIn("Hello, world", response.body, "Missing response.")

		# Stop the instance.
		runtime.stop(
			'1',
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until that's complete.
		self.wait()
		self.assertTrue(self.success)

		# Should not be running.
		runtime.status(
			'1',
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success)

		# And see if it's really stopped.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.assertNotEquals(response.code, 200)

		#print open(log_path, 'r').read()
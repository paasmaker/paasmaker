#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
		missing=20,
		default=20)
	standalone_wait = colander.SchemaNode(colander.Integer(),
		title="Standalone Wait",
		description="For standalone instances, wait this long for the instance to start before considering it running.",
		missing=5,
		default=5)

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
	API_VERSION = "0.9.0"

	def get_versions(self, callback):
		# Just return this version.
		callback(['1'])

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def start(self, instance_id, callback, error_callback):
		# Prepare the launch command.
		instance = self.configuration.instances.get_instance(instance_id)
		launch_params = {}
		port = None
		if instance['instance'].has_key('port'):
			port = instance['instance']['port']
			launch_params['port'] = instance['instance']['port']
		launch_command = self.parameters['launch_command'] % launch_params

		# Launch it.
		self._supervise_start(
			instance_id,
			launch_command,
			instance['runtime']['path'],
			instance['environment']
		)

		# Wait for it to start.
		def errored_out(message, exception=None):
			error_callback("Failed to start up instance inside timeout.", exception=exception)

		def timed_out(message):
			# Failed to start up in time. Stop the instance.
			self.logger.error("Timed out waiting for startup; stopping instance...")
			self.stop(instance_id, errored_out, errored_out)

		self._wait_for_startup(
			instance_id,
			instance['instance_type']['standalone'],
			port,
			self.parameters['start_timeout'],
			self.parameters['standalone_wait'],
			callback,
			timed_out,
			errored_out
		)

	def stop(self, instance_id, callback, error_callback):
		# Issue the stop command.
		try:
			self._supervise_stop(instance_id)
		except OSError, ex:
			# Probably no such PID. Failed!
			error_callback(str(ex), ex)
			return

		# Wait for it to free up the port, if it's not standalone.
		# If it's not standalone, wait for it to assume it's TCP port.
		instance = self.configuration.instances.get_instance(instance_id)

		def timeout(message):
			# Failed to stop listening, so it's not responding.
			# TODO: Handle this better.
			error_callback(message)

		port = None
		if instance['instance'].has_key('port'):
			port = instance['instance']['port']

		self._wait_for_shutdown(
			instance_id,
			instance['instance_type']['standalone'],
			port,
			self.parameters['start_timeout'],
			callback,
			timeout
		)

	def status(self, instance_id, callback, error_callback):
		if self._supervise_is_running(instance_id):
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

		instance.get_versions(self.stop)
		versions = self.wait()

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
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success)

		# Start it up.
		runtime.start(
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
		self.wait()
		self.assertTrue(self.success)

		# It should be running if we ask.
		runtime.status(
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
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until that's complete.
		self.wait()
		self.assertTrue(self.success)

		# Should not be running.
		runtime.status(
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

		# Try an instance that will fail immediately (and thus not assume the TCP port)
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'launch_command': 'python failure.py --port=%(port)d'
			}
		)

		# Start it up.
		runtime.start(
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
		self.wait()
		self.assertFalse(self.success)
		self.assertIn("timeout", self.message)

	def test_standalone(self):
		# Put together the barest of possible information to start up the system.
		instance_id = str(uuid.uuid4())
		instance = {}
		instance['instance'] = {'instance_id': instance_id}
		instance['instance_type'] = {'standalone': True}
		start_environment = {'PM_METADATA': '{}'}
		instance['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(self.configuration, start_environment)

		# Register the instance, and then configure the runtime parameters.
		self.configuration.instances.add_instance(instance_id, instance)
		instance['runtime']['path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/standalone-simple')

		# Now add the plugin, and instantiate.
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {}, 'Shell Runtime')
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'launch_command': 'python standalone.py',
				'standalone_wait': 1
			}
		)

		# For debugging, print out the log.
		log_path = self.configuration.get_job_log_path(instance_id)

		# Should not be running.
		runtime.status(
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success)

		# Start it up.
		runtime.start(
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
		self.wait()
		self.assertTrue(self.success)

		# It should be running if we ask.
		runtime.status(
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertTrue(self.success)

		#print open(log_path, 'r').read()

		# And see if it's really working.
		# TODO: This doesn't work - in the command
		# supervisor there are too many processes trying
		# to write to the same log file, which is causing issues.
		#log_contents = open(log_path, 'r').read()
		#self.assertIn("Starting standalone instance.", log_contents)

		# Stop the instance.
		runtime.stop(
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until that's complete.
		self.wait()
		self.assertTrue(self.success)

		# Should not be running.
		runtime.status(
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success)

		# Now try with an instance that will exit.
		# This should report a startup failure.
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'launch_command': 'python failure.py',
				'standalone_wait': 1
			}
		)

		# Start it up.
		runtime.start(
			instance_id,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
		self.wait()

		self.assertFalse(self.success)
		self.assertIn("Failed to start up instance inside timeout.", self.message)
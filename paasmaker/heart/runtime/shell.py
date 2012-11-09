
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
		description="The command to launch the instance. Substitutes %%(port)d with the allocated port.")

class ShellEnvironmentParametersSchema(colander.MappingSchema):
	# No options.
	pass

class ShellRuntime(BaseRuntime):
	MODES = [
		paasmaker.util.plugin.MODE.RUNTIME_STARTUP,
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS,
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT
	]
	OPTIONS_SCHEMA = ShellRuntimeOptionsSchema()
	PARAMETERS_SCHEMA = {
		paasmaker.util.plugin.MODE.RUNTIME_STARTUP: ShellRuntimeParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT: ShellEnvironmentParametersSchema()
	}

	def get_versions(self):
		# Just return this version.
		return ['1']

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def start(self, manager, instance_id, instance, callback, error_callback):
		# Generate the exit command and keys.
		self.generate_exit_report_command(self.configuration, manager, instance_id)
		# Create the start script.
		script = self.make_start_script(instance)
		# Get the log file for this instance id (using the job_id system).
		log_file = self.configuration.get_job_log_path(instance_id)
		log_fp = open(log_file, 'a')
		# Launch it.
		launcher = paasmaker.util.Popen(['bash', script],
			stdout=log_fp,
			stderr=log_fp,
			io_loop=self.configuration.io_loop,
			cwd=instance['runtime']['path'],
			env=instance['environment'])

		# Make a note of the PID.
		instance['runtime']['pid'] = launcher.pid
		manager.save()

		# Wait until the port is no longer free.
		# TODO: This won't work with standalone instances that don't use a TCP port.
		def wait_for_startup():
			if self.configuration.port_allocator.in_use(instance['instance']['port']):
				# And say that we're done.
				callback("Started.")
			else:
				# Wait a little bit longer.
				self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_startup)

		self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_startup)

	def stop(self, manager, instance_id, instance, callback, error_callback):
		# From the instance, kill the PID.
		os.kill(instance['runtime']['pid'], signal.SIGTERM)
		# Wait until the port is free.
		# TODO: This won't work with standalone instances that don't use a TCP port.
		def wait_for_shutdown():
			if not self.configuration.port_allocator.in_use(instance['instance']['port']):
				# And say that we're done.
				callback("Stopped instance.")
			else:
				# Wait a little bit longer.
				self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_shutdown)

		self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_shutdown)

	def status(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement stop.")

	def statistics(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement stop.")

	def make_start_script(self, instance):
		template = """
# Abort if any command fails.
set -xe
# And abort if a piped process fails.
set -o pipefail

# Launch the instance.
%(launch_command)s

# When it exits, grab the return code.
EXITCODE=$?

# Report the status.
curl "%(exit_url)s$EXITCODE"

"""
		start_script = tempfile.mkstemp()[1]

		fp = open(start_script, 'w')

		# Write out the launch command.
		launch_params = {}
		launch_params['port'] = instance['instance']['port']

		launch_command = self.parameters['launch_command'] % launch_params

		script_params = {}
		script_params['launch_command'] = launch_command
		script_params['exit_url'] = instance['runtime']['exit']['full_url']

		fp.write(template % script_params)

		fp.close()

		return start_script

class ShellRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(ShellRuntimeTest, self).setUp()

	def tearDown(self):
		super(ShellRuntimeTest, self).tearDown()

	def test_options(self):
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {})
		instance = self.configuration.plugins.instantiate('paasmaker.runtime.shell', paasmaker.util.plugin.MODE.RUNTIME_STARTUP, {'launch_command': 'test.py'})
		self.assertTrue(True, "Should have got here...")

	def test_versions(self):
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {})
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
		start_environment = {'PM_METADATA': '{}'}
		instance['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(self.configuration, start_environment)

		# Register the instance, and then configure the runtime parameters.
		self.configuration.instances.add_instance(instance_id, instance)
		instance['runtime']['path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')

		# Now add the plugin, and instantiate.
		self.configuration.plugins.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {})
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_STARTUP,
			{'launch_command': 'python app.py --port=%(port)d'}
		)

		runtime.start(
			self.configuration.instances,
			instance_id,
			instance,
			self.success_callback,
			self.failure_callback
		)

		# Wait until it's started.
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
			self.configuration.instances,
			instance_id,
			instance,
			self.success_callback,
			self.failure_callback
		)

		# Wait until that's complete.
		self.wait()
		self.assertTrue(self.success)

		# And see if it's really stopped.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		print str(response)

		self.failIf(response.error)

		print open(log_path, 'r').read()
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import subprocess
import re
import os
import shlex
import uuid
import glob

import paasmaker
from base import BaseRuntime, BaseRuntimeTest
import colander
import tornado

class StaticRuntimeOptionsSchema(colander.MappingSchema):
	config_dir = colander.SchemaNode(colander.String(),
		title="Apache Configuration directory",
		description="The directory to drop instance configuration files into. Must exist and be writable.",
		default="managed",
		missing="managed")
	graceful_command = colander.SchemaNode(colander.String(),
		title="Apache Graceful command",
		description="The command to graceful apache to add or remove instances.",
		default="sudo apache2ctl graceful",
		missing="sudo apache2ctl graceful")
	managed = colander.SchemaNode(colander.Boolean(),
		title="Manage Apache",
		description="If true, this plugin will maintain a managed version of apache for it's use, starting and stopping as required.",
		default=True,
		missing=True)
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown Manage Apache",
		description="If this plugin is managing an apache, it will shut it down when the server stops.",
		default=False,
		missing=False)

class StaticRuntimeParametersSchema(colander.MappingSchema):
	document_root = colander.SchemaNode(colander.String(),
		title="Document root",
		description="The subfolder under the application folder that is the document root.")

class StaticEnvironmentParametersSchema(colander.MappingSchema):
	# No options required, but the environment requires a schema.
	pass

class StaticRuntime(BaseRuntime):
	MODES = {
		paasmaker.util.plugin.MODE.RUNTIME_EXECUTE: StaticRuntimeParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT: StaticEnvironmentParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS: None,
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None,
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY: None
	}
	OPTIONS_SCHEMA = StaticRuntimeOptionsSchema()
	API_VERSION = "0.9.0"

	def _check_options(self):
		super(StaticRuntime, self)._check_options()
		# Set this correct path now, so status() works
		# properly without having to fetch the managed Apache.
		self.options['config_dir'] = self._get_config_path()

	VHOST_TEMPLATE = """
NameVirtualHost *:%(port)d
Listen %(port)d

<VirtualHost *:%(port)d>
	ServerName %(instance_id_servername)s
	DocumentRoot %(document_root)s
	ErrorLog %(error_log)s

	DirectoryIndex index.php index.html index.htm

	%(environment)s
</VirtualHost>
"""

	def get_versions(self, callback):
		callback(['1'])

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def _get_managed_path(self):
		directory = self.configuration.get_scratch_path(self.called_name)
		return directory

	def _get_config_path(self):
		return os.path.join(self._get_managed_path(), 'configuration')

	def _get_managed_instance(self, callback, error_callback):
		if self.options['managed']:
			self.apache_server = paasmaker.util.apachedaemon.ApacheDaemon(self.configuration)
			# This makes the directory named by the plugins registered name. So if you
			# have multiple static plugins with different names, you'll get one apache per
			# plugin.
			directory = self._get_managed_path()

			def on_configured(message):
				def on_apache_started(message):
					# Let the caller know we're ready.
					callback(message)

				def on_apache_failed(message, exception=None):
					error_callback(message, exception)

				try:
					self.apache_server.start_if_not_running(on_apache_started, on_apache_failed)
				except subprocess.CalledProcessError, ex:
					error_callback("Failed to start apache server.", exception=ex)
				# end of on_configured()

			# Set the config path.
			try:
				self.apache_server.load_parameters(directory)
				on_configured("Configured")
			except paasmaker.util.ManagedDaemonError, ex:
				# Doesn't yet exist. Create it.
				# TODO: This assigns a port from the instance pool... we probably then
				# should pre-allocate it on startup. So be a little careful here.
				port = self.configuration.get_free_port()
				self.apache_server.configure(
					directory,
					port,
					on_configured,
					error_callback
				)

		else:
			callback("No action to take.")

	def _shutdown_managed(self, callback, error_callback):
		if hasattr(self, 'apache_server'):
			self.apache_server.stop(callback, error_callback)
		else:
			callback("Nothing to shut down.")

	def _config_location(self, instance_id):
		path = self.options['config_dir']
		return os.path.join(path, '%s.conf' % instance_id)

	def _is_managed(self):
		return self.options['managed']

	def _configuration_for_instance(self, instance_id):
		instance = self.configuration.instances.get_instance(instance_id)
		# TODO: Make sure this document root can't escape the actual root.
		document_root = os.path.join(
			instance['runtime']['path'],
			self.parameters['document_root']
		)

		# TODO: This probably won't work with non-managed apaches...
		error_log_path = self.configuration.get_job_log_path(instance_id)

		# Set up any environment variables.
		# We don't need the whole environment, so just search for the ones
		# with JSON in them.
		env_list = []
		for key, value in instance['environment'].iteritems():
			if len(value) > 0 and value[0] == '{':
				env_list.append("SetEnv %s '%s'" % (key, value))

		configuration = self.VHOST_TEMPLATE % {
			'port': instance['instance']['port'],
			'document_root': document_root,
			'instance_id_servername': instance_id.replace("-", '.'),
			'error_log': error_log_path,
			'environment': "\n".join(env_list)
		}

		config_location = self._config_location(instance_id)
		fp = open(config_location, 'w')
		fp.write(configuration)
		fp.close()

	def start(self, instance_id, callback, error_callback):
		# First up, get our managed instance.
		def managed_server_up(message):
			instance = self.configuration.instances.get_instance(instance_id)

			# Ok, write out a configuration file.
			self._configuration_for_instance(instance_id)
			config_location = self._config_location(instance_id)

			def abort_startup(message, exception=None):
				# Something went wrong. Remove our configuration file,
				# and raise an error.
				os.unlink(config_location)
				error_callback("Failed to start up - port %d wasn't listening inside the timeout." % instance['instance']['port'])

			def on_graceful(message):
				# Wait for it to start listening.
				self.configuration.port_allocator.wait_until_port_used(
					self.configuration.io_loop,
					instance['instance']['port'],
					2.0, # Should not need more than 2 seconds. TODO: Tweak.
					callback, # On success, proceed to success.
					abort_startup
				)

			# Now, graceful the apache system.
			if self._is_managed():
				self.apache_server.graceful(on_graceful, abort_startup)
			else:
				# Run the graceful command supplied.
				# TODO: Make this async.
				output = subprocess.check_output(
					shlex.split(str(self.options['graceful_command'])),
					stderr=subprocess.STDOUT
				)

				if "error" in output:
					# It failed.
					os.unlink(config_location)
					error_callback("Failed to start up: " + output)
				else:
					on_graceful("Gracefulled")

		if self._is_managed():
			self._get_managed_instance(managed_server_up, error_callback)
		else:
			# Proceed directly as if the managed server is up.
			managed_server_up("Not managed.")

	def stop(self, instance_id, callback, error_callback):
		# First up, get our managed instance.
		def managed_server_up(message):
			# Unlink the configuration file.
			config_location = self._config_location(instance_id)
			os.unlink(config_location)

			def on_graceful(message):
				# Wait for it to stop listening.
				instance = self.configuration.instances.get_instance(instance_id)
				self.configuration.port_allocator.wait_until_port_free(
					self.configuration.io_loop,
					instance['instance']['port'],
					2.0, # Should not need more than 2 seconds. TODO: Tweak.
					callback, # On success, proceed to success.
					error_callback
				)

			# Now, graceful the apache system.
			if self._is_managed():
				self.apache_server.graceful(on_graceful, error_callback)
			else:
				# Run the graceful command supplied.
				# TODO: Make this async.
				subprocess.check_call(
					shlex.split(str(self.options['graceful_command']))
				)

				on_graceful("Graceful complete.")

		if self._is_managed():
			self._get_managed_instance(managed_server_up, error_callback)
		else:
			# Proceed directly as if the managed server is up.
			managed_server_up("Not managed.")

	def status(self, instance_id, callback, error_callback):
		# Check that the configuration file exists, and that
		# the port is in use.
		config_location = self._config_location(instance_id)
		if os.path.exists(config_location):
			instance = self.configuration.instances.get_instance(instance_id)
			in_use = self.configuration.port_allocator.in_use(instance['instance']['port'])
			if in_use:
				callback("Still running.")
			else:
				error_callback("Instance is configured, but not listening on it's assigned TCP port.")
		else:
			error_callback("Instance is not running - missing configuration file.")

	def statistics(self, instance_id, callback, error_callback):
		raise NotImplementedError("You must implement statistics.")

	def startup_async_prelisten(self, callback, error_callback):
		# If we're managed, set up and start up the managed apache instance.
		# But only if we have applications. Otherwise, no need to start it up -
		# we'll start it on demand.
		config_count = len(glob.glob("%s/*.conf" % self.options['config_dir']))
		if self._is_managed() and config_count > 0:
			self._get_managed_instance(callback, error_callback)
		else:
			callback("Startup of the managed Apache server not required on this node.")

	def shutdown_postnotify(self, callback, error_callback):
		# If we're managed, and been asked to shutdown the managed server,
		# do that.
		config_count = len(glob.glob("%s/*.conf" % self.options['config_dir']))
		if self._is_managed() and self.options['shutdown'] and config_count > 0:
			def on_stopped(message):
				callback("Stopped managed apache.")

			def got_managed(message):
				# Stop running the server.
				self.apache_server.stop(on_stopped, error_callback)

			self._get_managed_instance(got_managed, error_callback)
		else:
			callback("No managed apache to stop, or not required to shutdown.")

class StaticRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(StaticRuntimeTest, self).setUp()

		# Register the plugin.
		self.configuration.plugins.register(
			'paasmaker.runtime.static',
			'paasmaker.heart.runtime.StaticRuntime',
			{
				'shutdown': True
			},
			'Static File Runtime'
		)

	def tearDown(self):
		# Hack to kill any managed Apache instance.
		if hasattr(self, 'server'):
			if self.server.is_running():
				self.server.destroy(self.stop, self.stop)
				self.wait()

		super(StaticRuntimeTest, self).tearDown()

	def test_versions(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.static',
			paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
		)

		instance.get_versions(self.stop)
		versions = self.wait()

		self.assertEquals(len(versions), 1, "Shold have returned one value.")
		self.assertEquals(versions[0], '1', 'Wrong version returned.')

	def test_startup(self):
		# Put together the barest of possible information to start up the system.
		instance_id = str(uuid.uuid4())
		instance = {}
		instance['instance'] = {'instance_id': instance_id}
		instance['instance']['port'] = self.configuration.get_free_port()
		instance['instance_type'] = {'standalone': False}
		start_environment = {'PM_METADATA': '{"test":"bar"}'}
		instance['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(
			self.configuration,
			start_environment
		)

		# Register the instance, and then configure the runtime parameters.
		self.configuration.instances.add_instance(instance_id, instance)
		instance['runtime']['path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/static-simple')

		# Now add the plugin, and instantiate.
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.static',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'document_root': 'web'
			}
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
		self.wait(timeout=10)
		self.assertTrue(self.success, "Failed to start instance.")

		# Store the managed instance for later.
		self.server = runtime.apache_server

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

		self.failIf(response.error)
		self.assertIn("Hello, World", response.body, "Missing response.")

		# Check second page.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/page1.html" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.failIf(response.error)
		self.assertIn("Page 1", response.body, "Missing response.")

		# Shutdown the managed Apache.
		runtime.shutdown_postnotify(
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertTrue(self.success, "Managed apache did not shutdown successfully.")

		# The application won't be running any more.
		runtime.status(
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertFalse(self.success, "Managed apache did not shutdown - application still running.")

		# Start up the managed Apache.
		runtime.startup_async_prelisten(
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertTrue(self.success, "Did not shutdown correctly.")

		runtime.status(
			instance_id,
			self.success_callback,
			self.failure_callback
		)
		self.wait()
		self.assertTrue(self.success, "Managed apache did not restart - application not running.")

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
		self.assertFalse(self.success, "Application did not stop.")

		# And see if it's really stopped.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.assertNotEquals(response.code, 200)
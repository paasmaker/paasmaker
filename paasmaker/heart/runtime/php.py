
import subprocess
import re
import os
import shlex
import uuid

import paasmaker
from base import BaseRuntime, BaseRuntimeTest
import colander
import tornado

# TODO: Test the non-managed-apache code paths.
# TODO: Add open base dir restrictions option.
# TODO: Add APC enable/disable options.

class PHPRuntimeOptionsSchema(colander.MappingSchema):
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

class PHPRuntimeParametersSchema(colander.MappingSchema):
	document_root = colander.SchemaNode(colander.String(),
		title="Document root",
		description="The subfolder under the application folder that is the document root.")

class PHPEnvironmentParametersSchema(colander.MappingSchema):
	# No options required, but the environment requires a schema.
	pass

class PHPRuntime(BaseRuntime):
	MODES = {
		paasmaker.util.plugin.MODE.RUNTIME_EXECUTE: PHPRuntimeParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT: PHPEnvironmentParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS: None,
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None,
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY: None
	}
	OPTIONS_SCHEMA = PHPRuntimeOptionsSchema()

	VHOST_TEMPLATE = """
NameVirtualHost *:%(port)d
Listen %(port)d

<VirtualHost *:%(port)d>
	ServerName %(instance_id_servername)s
	DocumentRoot %(document_root)s
	ErrorLog %(error_log)s

	%(environment)s
</VirtualHost>
"""

	def get_versions(self, callback):
		try:
			raw_version = subprocess.check_output(['php', '-v'])
			# Parse out the version number.
			match = re.match(r'PHP ([\d.]+)', raw_version)
			if match:
				version = match.group(1)
				bits = version.split(".")
				major_version = ".".join(bits[0:2])

				callback([major_version, version])
			else:
				# No versions available.
				callback([])
		except subprocess.CalledProcessError, ex:
			# This means PHP didn't exist.
			callback([])

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def _get_managed_instance(self, callback, error_callback):
		if self.options['managed']:
			self.apache_server = paasmaker.util.managedapache.ManagedApache(self.configuration)
			# This makes the directory named by the plugins registered name. So if you
			# have multiple PHP plugins with different names, you'll get one apache per
			# plugin.
			directory = self.configuration.get_scratch_path(self.called_name)

			# Set the config path.
			try:
				self.apache_server.load_parameters(directory)
			except paasmaker.util.ManagedDaemonError, ex:
				# Doesn't yet exist. Create it.
				# TODO: This assigns a port from the instance pool... we probably then
				# should pre-allocate it on startup. So be a little careful here.
				port = self.configuration.get_free_port()
				self.apache_server.configure(
					directory,
					port
				)

			def on_apache_started(message):
				# Set the config dir for later.
				self.options['config_dir'] = self.apache_server.get_config_dir()
				# Let the caller know we're ready.
				callback(message)

			def on_apache_failed(message, exception=None):
				error_callback(message, exception)

			try:
				self.apache_server.start_if_not_running(on_apache_started, on_apache_failed)
			except subprocess.CalledProcessError, ex:
				error_callback("Failed to start apache server.", exception=ex)
		else:
			callback("No action to take.")

	def _shutdown_managed(self):
		if hasattr(self, 'apache_server'):
			self.apache_server.stop()

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

			# Now, graceful the apache system.
			if self._is_managed():
				output = self.apache_server.graceful()
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
				return

			def abort_startup(message, exception=None):
				# Something went wrong. Remove our configuration file,
				# and raise an error.
				os.unlink(config_location)
				error_callback("Failed to start up - port %d wasn't listening inside the timeout." % instance['instance']['port'])

			# Wait for it to start listening.
			self.configuration.port_allocator.wait_until_port_used(
				self.configuration.io_loop,
				instance['instance']['port'],
				2.0, # Should not need more than 2 seconds. TODO: Tweak.
				callback, # On success, proceed to success.
				abort_startup
			)

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

			# Now, graceful the apache system.
			if self._is_managed():
				self.apache_server.graceful()
			else:
				# Run the graceful command supplied.
				# TODO: Make this async.
				subprocess.check_call(
					shlex.split(str(self.options['graceful_command']))
				)

			# Wait for it to stop listening.
			instance = self.configuration.instances.get_instance(instance_id)
			self.configuration.port_allocator.wait_until_port_free(
				self.configuration.io_loop,
				instance['instance']['port'],
				2.0, # Should not need more than 2 seconds. TODO: Tweak.
				callback, # On success, proceed to success.
				error_callback # Or error...
			)

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
		if self._is_managed():
			self._get_managed_instance(callback, error_callback)

	def shutdown_postnotify(self, callback, error_callback):
		# If we're managed, and been asked to shutdown the managed server,
		# do that.
		if self._is_managed() and self.options['shutdown']:
			def got_managed(message):
				# Stop running the server.
				self.apache_server.stop()
				callback("Stopped managed apache.")
			self._get_managed_instance(got_managed, error_callback)
		else:
			callback("No managed apache to stop.")

class PHPRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(PHPRuntimeTest, self).setUp()

		# Register the plugin.
		self.configuration.plugins.register(
			'paasmaker.runtime.php',
			'paasmaker.heart.runtime.PHPRuntime',
			{},
			'PHP Runtime'
		)

	def tearDown(self):
		# Hack to kill any managed Apache instance.
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.php',
			paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
		)
		instance._get_managed_instance(self.stop, self.stop)
		self.wait()
		instance._shutdown_managed()

		super(PHPRuntimeTest, self).tearDown()

	def test_versions(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.php',
			paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
		)

		instance.get_versions(self.stop)
		versions = self.wait()

		comparison = subprocess.check_output(['php', '-v'])
		self.assertEquals(len(versions), 2, "Should have returned two values.")
		self.assertEquals(versions[0], versions[1][0:len(versions[0])], "First version should have been substring of later version.")
		for version in versions:
			self.assertIn(".", version, "Version is not properly qualified.")
			self.assertIn(version, comparison, "Missing version in output.")

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
		instance['runtime']['path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/php-simple')

		# Now add the plugin, and instantiate.
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.php',
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

		self.failIf(response.error)
		self.assertIn("Hello, world", response.body, "Missing response.")

		# Check environment variables.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/environ.php" % instance['instance']['port']
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.failIf(response.error)
		self.assertIn("PM_METADATA", response.body, "Missing response.")

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
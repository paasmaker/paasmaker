import uuid
import time

import paasmaker

import tornado.testing

# Base runtime interface.
class BaseRuntime(paasmaker.util.plugin.Plugin):

	def get_versions(self, callback):
		"""
		Get the versions that this runtime supports. Call the supplied
		callback with an list of versions that it supports. Emit
		an empty list if your node does not support this runtime - this
		will cause the node not to be matched when searching for a node
		that can run an application.

		A good practice is to emit several versions for major and minor
		types. For example, the PHP runtime emits '5.3' and '5.3.6' so
		either a major version or a minor version can be targeted. The
		Ruby runtime does the same thing, for example it emits '1.9.3' and
		'1.9.3-p327'.

		For example::

			def get_versions(self, callback):
				versions = ['1', '1.1']
				callback(versions)

		If you need to call out to an external process to determine the versions,
		you should do so on the Tornado IO loop, and call the callback when ready.

		This is called early on in server startup, to gather a list of
		runtime versions that this node supports before registering with the
		master node. The results of this are cached after the first time
		after server startup.

		:arg callable callback: The callback to call once done.
		"""
		raise NotImplementedError("You must implement get_versions().")

	def environment(self, version, environment, callback, error_callback):
		"""
		Set up any environment required to run this runtime. This assumes
		that the runtime can just do its work via altering the environment.
		You should mutate the supplied environment, and call the callback
		when you're done with a simple message.

		For example::

			def environment(self, version, environment, callback, error_callback):
				environment['PATH'] = "/path/to/my/runtime-%s:%s" % (version, environment['PATH'])
				callback("Ready.")

		:arg str version: The version that the application requested.
		:arg dict environment: A dictionary of the current application environment,
			that you should modify directly.
		:arg callable callback: The success callback.
		:arg callable error_callback: The error callback.
		"""
		raise NotImplementedError("You must implement environment().")

	def start(self, instance_id, callback, error_callback):
		"""
		Start the given instance of this application.

		You can fetch the full instance data with the following code::

			instance = self.configuration.instances.get_instance(instance_id)
			tcp_port = instance['instance']['port']

		Call the supplied callback with a simple message on success.
		Success is defined as the application is running and listening
		on the assigned TCP port for HTTP traffic.

		Call the error_callback with a message and optionally
		an exception if you are unable to start the instance.

		:arg str instance_id: The instance ID to start.
		:arg callable callback: The callback for success.
		:arg callable error_callback: The error callback.
		"""
		raise NotImplementedError("You must implement start().")

	def stop(self, instance_id, callback, error_callback):
		"""
		Stop the given instance of this application.

		Call the supplied callback with a simple message on success.
		Success is defined as the application is no longer running and
		is not listening on the assigned TCP port.

		Call the error_callback with a message and optionally
		an exception if you are unable to start the instance.

		:arg str instance_id: The instance ID to stop.
		:arg callable callback: The callback for success.
		:arg callable error_callback: The error callback.
		"""
		raise NotImplementedError("You must implement stop().")

	def status(self, instance_id, callback, error_callback):
		"""
		Determine the status of this instance. If the instance
		is running, call the callback with a simple message saying
		that everything is ok. If it is not running, call the error_callback
		with a message that may assist with finding the reason why
		it's not running.

		:arg str instance_id: The instance ID to query.
		:arg callable callback: The callback for success.
		:arg callable error_callback: The error callback.
		"""
		raise NotImplementedError("You must implement status().")

	def statistics(self, instance_id, callback, error_callback):
		"""
		NOTE: This is currently not used by Paasmaker.

		Generate some application instance statistics.
		You should at least return a dict containing:
		cpu_percent: CPU usage, percent, most recent.
		memory: memory used, bytes.
		cpu_time: CPU usage, in seconds total.
		If you're unable to gather this information, return zero
		for the figures.
		"""
		raise NotImplementedError("You must implement statistics().")

	def _generate_exit_report_command(self, instance_id):
		"""
		Generate an exit report command that can be used by runtimes
		to report that they've exited or changed state to the heart.
		There are quite a few keys returned, allowing the runtime
		to use a few different options to implement this. This is
		designed to be used by the command supervisor.

		The data is stored back in the instance manager's data store.
		You can access what it returns like so::

			instance = self.configuration.instances.get_instance(instance_id)
			# keys will be a list of valid keys.
			keys = instance['runtime']['exit']['keys']
			# url is a relative URL (eg, /instance/exit/...)
			url = instance['runtime']['exit']['url']
			# full_url is a complete URL that can be called by curl or others.
			# It will be like http://localhost:port/instance/exit/...)
			full_url = instance['runtime']['exit']['full_url']

		:arg str instance_id: The instance ID to generate the exit
			report commands for.
		"""
		instance = self.configuration.instances.get_instance(instance_id)
		unique_key = str(uuid.uuid4())
		# CAUTION: The URL still needs the process exit code
		# appended to the end of it to be the full URL.
		url = '/instance/exit/%s/%s/' % (instance_id, unique_key)
		full_url = 'http://localhost:%d%s' % (self.configuration.get_flat('http_port'), url)

		if not instance['runtime'].has_key('exit'):
			instance['runtime']['exit'] = {}
		if not instance['runtime']['exit'].has_key('keys'):
			instance['runtime']['exit']['keys'] = []

		instance['runtime']['exit']['keys'].append(unique_key)
		instance['runtime']['exit']['url'] = url
		instance['runtime']['exit']['full_url'] = full_url

		self.configuration.instances.save()

	def _supervise_start(self, instance_id, command, cwd, environment):
		"""
		Using the command supervisor, start the given command for the given
		instance id. Returns regardless of startup status; you should wait
		for startup using ``_wait_for_startup``. If the command exits, it will
		report it's status via the API.

		:arg str instance_id: The instance ID to start.
		:arg str command: The command to start the instance.
		:arg str cwd: The working directory for the command.
		:arg dict environment: The environment to pass to the instance when it starts.
		"""
		self._generate_exit_report_command(instance_id)

		supervisor = paasmaker.util.CommandSupervisorLauncher(self.configuration, instance_id)
		instance = self.configuration.instances.get_instance(instance_id)
		instance['runtime']['supervised'] = True
		self.configuration.instances.save()

		# Fetch the first key.
		exit_key = instance['runtime']['exit']['keys'][0]
		# And fire it off.
		supervisor.launch(command, cwd, environment, exit_key, self.configuration.get_flat('http_port'))

	def _wait_for_startup(self, instance_id, standalone, port, tcp_timeout, standalone_wait, callback, timeout_callback, error_callback):
		"""
		Wait for the given instance to start up.

		For normal instances, it waits for the supplied TCP port to be in use.
		It calls the timeout_callback if it doesn't assume the TCP port in time.
		It calls the error_callback if the process dies before it assumes the TCP port
		(so if it has an error on startup). It calls the callback if the process
		assumes the TCP port correctly.

		For standalone instances, it will give it standalone_wait seconds to start,
		and then check it's status, and feed back the appropriate status based
		on the instance. To be considered as started, the process has to exist,
		although it might not yet be ready to do what it's meant to do (for example,
		if the instance takes a while to prepare itself).

		:arg str instance_id: The instance ID to wait for.
		:arg bool standalone: If the instance is standalone or not.
		:arg int|None port: The TCP port that the instance should be assuming, if it's
			not standalone.
		:arg int tcp_timeout: The length of time to wait for it to assume the TCP
			port. Only applies if it's not standalone.
		:arg int standalone_wait: Wait this long for a standalone instance to start up.
			This gives that instance time to settle, but does delay startup.
		:arg callable callback: The callback to call when it's running.
		:arg callable timeout_callback: The callback to call when the startup
			times out.
		:arg callable error_callback: The callback to call when the startup
			fails, because the subprocess dies.
		"""
		# In a loop, wait for either the process to die (it gave an error)
		# or for it to assume the appropriate TCP port.
		end_timeout = time.time() + tcp_timeout

		def wait_for_state():
			process_running = self._supervise_is_running(instance_id)
			if not standalone:
				port_in_use = self.configuration.port_allocator.in_use(port)

			if not process_running:
				# It errored.
				error_callback("Process is no longer running.")
				return
			if standalone and process_running:
				# It's running.
				callback("Process is running.")
				return
			if not standalone and port_in_use:
				# It's running.
				callback("Port is now in use.")
				return
			if time.time() > end_timeout:
				timeout_callback("Failed to end up in appropriate state in time.")
				return

			self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

		if standalone:
			# Wait for the appropriate time before checking the instance.
			self.configuration.io_loop.add_timeout(time.time() + standalone_wait, wait_for_state)
		else:
			self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

	def _supervise_stop(self, instance_id):
		"""
		Using the command supervisor, stop the given instance. If it was
		not started using the supervisor, things will go wrong. This returns
		immediately; you should use ``_wait_for_shutdown`` to wait for it to exit.

		:arg str instance_id: The instance ID to stop.
		"""
		supervisor = paasmaker.util.CommandSupervisorLauncher(self.configuration, instance_id)
		supervisor.kill()

	def _wait_for_shutdown(self, instance_id, standalone, port, timeout, callback, timeout_callback):
		"""
		Wait for the given instance to shut down.

		For normal instances, it waits for the supplied TCP port to be free.
		It calls the timeout_callback if it doesn't release the TCP port inside the timeout.

		For standalone instances, it will call the callback as soon as the instance
		is no longer running, or the timeout callback if it doesn't stop.

		:arg str instance_id: The instance ID to wait for.
		:arg bool standalone: If the instance is standalone or not.
		:arg int timeout: How long to wait for shutdown.
		:arg callable callback: The callback to call when it's stopped.
		:arg callable timeout_callback: The callback to call when the shutdown
			times out.
		"""
		end_timeout = time.time() + timeout

		def wait_for_state():
			process_running = self._supervise_is_running(instance_id)
			if not standalone:
				port_in_use = self.configuration.port_allocator.in_use(port)

			if not process_running:
				# It finished.
				# See if the port is free.
				if not standalone and not port_in_use:
					# Port is free.
					callback("Port is now free.")
					return
				elif standalone:
					# Finished.
					callback("Process is finished.")
					return

			if time.time() > end_timeout:
				timeout_callback("Failed to end up in appropriate state in time.")
				return

			self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

		self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

	def _supervise_is_running(self, instance_id):
		"""
		Determine if the supervised command is still running or not.
		Returns True if it is, or False otherwise.

		:arg str instance_id: The instance ID to check.
		"""
		supervisor = paasmaker.util.CommandSupervisorLauncher(self.configuration, instance_id)
		return supervisor.is_running()

class BaseRuntimeTest(paasmaker.common.controller.BaseControllerTest):
	config_modules = ['heart']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = paasmaker.heart.controller.InstanceExitController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def setUp(self):
		super(BaseRuntimeTest, self).setUp()
		self.success = None
		self.message = None

	def tearDown(self):
		super(BaseRuntimeTest, self).tearDown()

	def success_callback(self, message):
		self.success = True
		self.message = message
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.stop()

	def _get_error_log(self, instance_id):
		error_path = self.configuration.get_job_log_path(instance_id)
		return error_path
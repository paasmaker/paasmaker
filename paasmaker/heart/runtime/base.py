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
		an empty list if your node does not support this runtime.
		"""
		raise NotImplementedError("You must implement get_versions().")

	def environment(self, version, environment, callback, error_callback):
		"""
		Set up any environment required to run this runtime. This assumes
		that the runtime can just do it's work via an environment. You
		should mutate the supplied environment, and call the callback
		when you're done.
		"""
		raise NotImplementedError("You must implement environment().")

	def start(self, instance_id, callback, error_callback):
		"""
		Start the given instance of this application.
		"""
		raise NotImplementedError("You must implement start().")

	def stop(self, instance_id, callback, error_callback):
		"""
		Stop the given instance of this application.
		"""
		raise NotImplementedError("You must implement stop().")

	def status(self, instance_id, callback, error_callback):
		"""
		Determine the status of this instance. Call the callback
		with a message if it's ok, or the error_callback with
		(message, exception) if not.
		"""
		raise NotImplementedError("You must implement status().")

	def statistics(self, instance_id, callback, error_callback):
		"""
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
		to use a few different options to implement this.
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
		instance id. Returns regardless of startup status; the command
		will report it's exit via the API.
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
		on the instance.

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
		not started using the supervisor, things will go wrong.
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
				callback("Process is finished.")
				return
			if not standalone and not port_in_use:
				# Port is free.
				callback("Port is now free.")
				return
			if time.time() > end_timeout:
				timeout_callback("Failed to end up in appropriate state in time.")
				return

			self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

		self.configuration.io_loop.add_timeout(time.time() + 0.2, wait_for_state)

	def _supervise_is_running(self, instance_id):
		"""
		Determine if the supervised command is still running or not.
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
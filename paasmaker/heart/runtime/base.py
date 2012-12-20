import uuid
import time

import paasmaker

import tornado.testing

# Base runtime interface.
class BaseRuntime(paasmaker.util.plugin.Plugin):

	def get_versions(self):
		"""
		Get the versions that this runtime supports. Return an array
		of versions.
		"""
		# NOTE: This is not asynchronous, so you probably don't want to
		# spend a long time doing anything.
		pass

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

	def generate_exit_report_command(self, instance_id):
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

	def supervise_start(self, instance_id, command, cwd, environment):
		"""
		Using the command supervisor, start the given command for the given
		instance id. Returns regardless of startup status; the command
		will report it's exit via the API.
		"""
		self.generate_exit_report_command(instance_id)

		supervisor = paasmaker.util.CommandSupervisorLauncher(self.configuration, instance_id)
		instance = self.configuration.instances.get_instance(instance_id)
		instance['runtime']['supervised'] = True
		self.configuration.instances.save()

		# Fetch the first key.
		exit_key = instance['runtime']['exit']['keys'][0]
		# And fire it off.
		supervisor.launch(command, cwd, environment, exit_key, self.configuration.get_flat('http_port'))

	def wait_until_port_used(self, port, timeout, callback, timeout_callback):
		self.wait_until_port_state(port, True, timeout, callback, timeout_callback)
	def wait_until_port_free(self, port, timeout, callback, timeout_callback):
		self.wait_until_port_state(port, False, timeout, callback, timeout_callback)

	def wait_until_port_state(self, port, state, timeout, callback, timeout_callback):
		# Wait until the port is no longer free.
		end_timeout = time.time() + timeout

		def wait_for_state():
			if self.configuration.port_allocator.in_use(port) == state:
				# And say that we're done.
				callback("In appropriate state.")
			else:
				if time.time() > end_timeout:
					timeout_callback("Failed to end up in appropriate state in time.")
				else:
					# Wait a little bit longer.
					self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_state)

		self.configuration.io_loop.add_timeout(time.time() + 0.1, wait_for_state)

	def supervise_stop(self, instance_id):
		"""
		Using the command supervisor, stop the given instance. If it was
		not started using the supervisor, things will go wrong.
		"""
		supervisor = paasmaker.util.CommandSupervisorLauncher(self.configuration, instance_id)
		supervisor.kill()

	def supervise_is_running(self, instance_id):
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
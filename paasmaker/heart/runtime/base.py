import uuid

import paasmaker
#from ..testhelpers import TestHelpers

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

	def start(self, manager, instance_id, instance, callback, error_callback):
		"""
		Start the given instance of this application. Instance is a
		dict of data from the instance manager. You should not mutate
		any of it, except for the runtime dict to keep a track of anything
		you want to know.
		"""
		raise NotImplementedError("You must implement start().")

	def stop(self, manager, instance_id, instance, callback, error_callback):
		"""
		Stop the given instance of this application.
		"""
		raise NotImplementedError("You must implement stop().")

	def status(self, manager, instance_id, instance, callback, error_callback):
		"""
		Determine the status of this instance.
		"""
		raise NotImplementedError("You must implement status().")

	def statistics(self, manager, instance_id, instance, callback, error_callback):
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

	def generate_exit_report_command(self, configuration, manager, instance_id):
		"""
		Generate an exit report command that can be used by runtimes
		to report that they've exited or changed state to the heart.
		There are quite a few keys returned, allowing the runtime
		to use a few different options to implement this.
		"""
		instance = manager.get_instance(instance_id)
		unique_key = str(uuid.uuid4())
		# CAUTION: The URL still needs the process exit code
		# appended to the end of it to be the full URL.
		url = '/instance/exit/%s/%s/' % (instance_id, unique_key)
		full_url = 'http://localhost:%d%s' % (configuration.get_flat('http_port'), url)

		if not instance['runtime'].has_key('exit'):
			instance['runtime']['exit'] = {}
		if not instance['runtime']['exit'].has_key('keys'):
			instance['runtime']['exit']['keys'] = []

		instance['runtime']['exit']['keys'].append(unique_key)
		instance['runtime']['exit']['url'] = url
		instance['runtime']['exit']['full_url'] = full_url

		manager.save()

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

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.stop()
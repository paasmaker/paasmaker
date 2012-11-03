
import subprocess
import re

import paasmaker
from base import BaseRuntime, BaseRuntimeTest
import colander

class ShellRuntimeOptionsSchema(colander.MappingSchema):
	# No options.
	pass

class ShellRuntimeParametersSchema(colander.MappingSchema):
	# No options.
	pass

class ShellRuntime(BaseRuntime):
	MODES = [
		paasmaker.util.plugin.MODE.RUNTIME_STARTUP,
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS,
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT
	]
	OPTIONS_SCHEMA = ShellRuntimeOptionsSchema()
	PARAMETERS_SCHEMA = ShellRuntimeParametersSchema()

	def get_versions(self):
		# Just return this version.
		return ['1']

	def environment(self, version, environment, callback, error_callback):
		# Nothing to set up - so just proceed.
		callback("Ready.")

	def start(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement start.")

	def stop(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement stop.")

	def status(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement stop.")

	def statistics(self, manager, instance_id, instance, callback, error_callback):
		raise NotImplementedError("You must implement stop.")

class ShellRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(ShellRuntimeTest, self).setUp()

	def tearDown(self):
		super(ShellRuntimeTest, self).tearDown()

	def test_options(self):
		self.registry.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {})
		instance = self.registry.instantiate('paasmaker.runtime.shell', paasmaker.util.plugin.MODE.RUNTIME_STARTUP, {})
		self.assertTrue(True, "Should have got here...")

	def test_versions(self):
		self.registry.register('paasmaker.runtime.shell', 'paasmaker.heart.runtime.ShellRuntime', {})
		instance = self.registry.instantiate('paasmaker.runtime.shell', paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)

		versions = instance.get_versions()

		self.assertEquals(len(versions), 1, "More than one version?")
		self.assertEquals(versions[0], "1", "Wrong version returned.")
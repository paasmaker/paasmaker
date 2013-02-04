
import subprocess
import os
import signal
import re
import uuid
import tempfile
import time
import glob

import paasmaker
from base import BaseRuntime, BaseRuntimeTest

import colander
import tornado

class RbenvRuntimeOptionsSchema(colander.MappingSchema):
	rbenv_path = colander.SchemaNode(colander.String(),
		title="rbenv path",
		description="The path to the root where rbenv is installed.",
		default="~/.rbenv",
		missing="~/.rbenv")

class RbenvRuntimeParametersSchema(colander.MappingSchema):
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

class RbenvEnvironmentParametersSchema(colander.MappingSchema):
	# No options.
	pass

class RbenvRuntime(BaseRuntime):
	MODES = {
		paasmaker.util.plugin.MODE.RUNTIME_EXECUTE: RbenvRuntimeParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT: RbenvEnvironmentParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_VERSIONS: None
	}
	OPTIONS_SCHEMA = RbenvRuntimeOptionsSchema()
	API_VERSION = "0.9.0"

	def _get_rbenv_root_path(self):
		raw_path = self.options['rbenv_path']
		# Expand the path. This is done so it can be relative to the
		# running users home dir for pure convenience and simplicity,
		# or an absolute path if required.
		return os.path.expanduser(raw_path)

	def get_versions(self, callback, include_majors=True):
		# From the directory, glob out a set of versions.
		path = self._get_rbenv_root_path()
		version_path = os.path.join(path, 'versions')

		self.logger.debug("Rbenv versions path: %s", version_path)

		# When we glob, we're doing this:
		#  ~/.rbenv/versions/*/bin/ruby
		# Looking for the ruby executable saves some accidents
		# if you're still installing that version of ruby
		# and it's not yet ready for production.
		raw_result = glob.glob(os.path.join(version_path, '*', 'bin', 'ruby'))
		self.logger.debug("Found %d versions of ruby.", len(raw_result))

		# Process the results.
		versions = set()

		version_start = len(version_path) + 1
		version_postfix = os.path.join('/', 'bin', 'ruby')
		for version_path in raw_result:
			version_end = version_path.rfind(version_postfix)
			version = version_path[version_start:version_end]

			if include_majors:
				# Split into major/minor versions, and advertise both.
				# TODO: Decide if this is a good idea or not... probably not.
				bits = version.split("-p")
				if len(bits) == 1:
					# Only the major version.
					versions.add(bits[0])
				else:
					# Major and minor versions.
					versions.add(bits[0])
					versions.add(version)
			else:
				versions.add(version)

		output_versions = list(versions)
		output_versions.sort()

		callback(output_versions)

	def _locate_version(self, version, callback, candidates=None):
		def got_versions(versions):
			# Does the exact version exist already?
			if version in versions:
				# Yes! Return it.
				callback(version)
				return
			else:
				# Not exactly. Let's search for the highest
				# closest version match.
				versions.reverse()
				for possible_version in versions:
					if possible_version.startswith(version):
						# Found it. Because the list
						# was sorted, this should be
						# the highest version.
						callback(possible_version)
						return

				# If we got here, we didn't find a match.
				callback(None)

			# end of got_versions()

		# Get a list of available versions.
		if candidates:
			got_versions(candidates)
		else:
			versions = self.get_versions(got_versions, include_majors=False)

	def environment(self, version, environment, callback, error_callback):
		# To get rbenv to work, all we need to do is to
		# adjust two environment variables:
		#   RBENV_VERSION=<version>
		#   PATH=<rbenv stub path>:PATH

		def located_version(real_version):
			if not real_version:
				# Can't find a version to match this.
				error_message = "Unable to find version %s on this node." % version
				self.logger.error(error_message)
				error_callback(error_message)
				return

			self.logger.info("Using version %s (requested %s)", real_version, version)

			environment['RBENV_VERSION'] = real_version
			if not environment.has_key('PATH'):
				error_message = "The environment is missing a PATH variable. This is unusual, so not continuing."
				self.logger.error(error_message)
				error_callback(error_message)
				return

			# TODO: Check if we're adding it again and don't do that.
			environment['PATH'] = "%s:%s:%s" % (
				os.path.join(self._get_rbenv_root_path(), 'shims'),
				os.path.join(self._get_rbenv_root_path(), 'bin'),
				environment['PATH']
			)

			callback("Ready to run version %s." % real_version)

			# end of located_version()

		# First, locate an appropriate version.
		self._locate_version(version, located_version)

	def start(self, instance_id, callback, error_callback):
		# Prepare the launch command.
		instance = self.configuration.instances.get_instance(instance_id)
		launch_params = {}
		port = None
		if instance['instance'].has_key('port'):
			port = instance['instance']['port']
			launch_params['port'] = instance['instance']['port']
		launch_command = self.parameters['launch_command'] % launch_params

		def environment_prepared(message):
			# Launch it.
			self._supervise_start(
				instance_id,
				launch_command,
				instance['runtime']['path'],
				instance['environment']
			)

			def errored_out(message):
				error_callback("Failed to start up instance inside timeout.")

			def timed_out(message):
				# Failed to start up in time. Stop the instance.
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

			# end of environment_prepared()

		# Set up the environment for this version.
		self.environment(
			instance['instance_type']['runtime_version'],
			instance['environment'],
			environment_prepared,
			error_callback
		)

	def stop(self, instance_id, callback, error_callback):
		# Issue the stop command.
		try:
			self._supervise_stop(instance_id)
		except OSError, ex:
			# Probably no such PID. Failed!
			error_callback(str(ex), ex)
			return

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

class RbenvRuntimeTest(BaseRuntimeTest):

	def setUp(self):
		super(RbenvRuntimeTest, self).setUp()

		# If rbenv is not installed, skip this test.
		if not os.path.exists(os.path.expanduser('~/.rbenv')):
			self.skipTest("rbenv is not installed, so can't test this runtime.")

		self.configuration.plugins.register(
			'paasmaker.runtime.ruby.rbenv',
			'paasmaker.heart.runtime.RbenvRuntime',
			{},
			'Ruby RBEnv Runtime'
		)

	def tearDown(self):
		super(RbenvRuntimeTest, self).tearDown()

	def test_options(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.shell',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'launch_command': 'test.py'
			}
		)
		self.assertTrue(True, "Should have got here...")

	def test_versions(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.ruby.rbenv',
			paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
		)

		instance.get_versions(self.stop)
		versions = self.wait()

		self.assertTrue(len(versions) >= 2, "Not enough versions.")

	def test_versions(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.ruby.rbenv',
			paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
		)

		# Given a list of candidate versions, make sure it picks the right one.
		versions = ['1.9.2-p190', '1.9.3-p120', '1.9.3-p140']

		instance._locate_version('1.9.3', self.stop, versions)
		real_version = self.wait()
		self.assertEquals(real_version, '1.9.3-p140', 'Wrong version selected.')

		instance._locate_version('1.9.3-p120', self.stop, versions)
		real_version = self.wait()
		self.assertEquals(real_version, '1.9.3-p120', 'Wrong version selected.')

		instance._locate_version('1.9.2', self.stop, versions)
		real_version = self.wait()
		self.assertEquals(real_version, '1.9.2-p190', 'Wrong version selected.')

		instance._locate_version('1.9.1', self.stop, versions)
		real_version = self.wait()
		self.assertEquals(real_version, None, 'Wrong version selected.')

	def test_environment(self):
		instance = self.configuration.plugins.instantiate(
			'paasmaker.runtime.ruby.rbenv',
			paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT,
			{}
		)

		environment = {'PATH': ''}

		instance.environment('1.9.3', environment, self.success_callback, self.failure_callback)

		self.assertTrue(self.success, "Did not succeed.")
		self.assertTrue(environment.has_key('RBENV_VERSION'), "Missing RBENV_VERSION in output.")
		self.assertTrue('1.9.3-p' in environment['RBENV_VERSION'], "Missing specific version.")

	def test_startup(self):
		# Put together the barest of possible information to start up the system.
		instance_id = str(uuid.uuid4())
		instance = {}
		instance['instance'] = {'instance_id': instance_id}
		instance['instance']['port'] = self.configuration.get_free_port()
		instance['instance_type'] = {
			'standalone': False,
			'runtime_version': '1.9.3'
		}
		start_environment = {'PM_METADATA': '{}'}
		instance['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(
			self.configuration,
			start_environment
		)

		# Register the instance, and then configure the runtime parameters.
		self.configuration.instances.add_instance(instance_id, instance)
		instance['runtime']['path'] = os.path.normpath(
			os.path.dirname(__file__) + '/../../../misc/samples/sinatra-simple'
		)

		# Now add the plugin, and instantiate.
		runtime = self.configuration.plugins.instantiate(
			'paasmaker.runtime.ruby.rbenv',
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
			{
				'launch_command': 'bundle exec ruby app.rb -p %(port)d'
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
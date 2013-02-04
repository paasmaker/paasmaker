
import os
import re
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest
import uuid

import paasmaker
from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado.testing

class PostgresDaemonError(ManagedDaemonError):
	pass

class PostgresDaemon(ManagedDaemon):
	"""
	Start and manage a Postgres daemon in a custom data
	directory, for use by other services/plugins.

	If you provide a password to the configure method,
	the user 'postgres' will have that password. From there,
	you can interact with the daemon as normal.

	You should use a port other than 5432 for it, so as to
	not conflict with any system installation of Postgres.
	"""

	def _eat_output(self):
		return open("%s/%s" % (self.parameters['working_dir'], str(uuid.uuid4())), 'w')

	def configure(self, working_dir, postgres_binaries_path, port, bind_host, password=None):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg str postgres_binaries_path: The path to the binaries for Postgres.
		:arg int port: The port to listen on.
		:arg str bind_host: The address to bind to.
		:arg str|None password: An optional password for the
			postgres user.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['postgres_binaries_path'] = postgres_binaries_path
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		self.parameters['password'] = password

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		# Now, we actually need to run pg_ctl initdb to get it all set up.
		command_line = "%s -D %s --username=postgres" % (
			os.path.join(self.parameters['postgres_binaries_path'], 'initdb'),
			working_dir
		)

		pwfile = None
		if password:
			pwfile = tempfile.mkstemp()[1]
			open(pwfile, 'w').write(password)
			command_line += ' --auth=md5 --pwfile=' + pwfile

		command_line += " > /tmp/initdb.log 2>&1"

		# Go ahead and create it.
		subprocess.check_call(
			command_line,
			shell=True
		)

		if pwfile:
			os.unlink(pwfile)

		self.save_parameters()

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Fire up the server.
		logging.info("Starting up postgres server on port %d." % self.parameters['port'])

		# Use a string here isntead of an array, because it was munging the
		# sub arguments.
		command_line = "%s start -D %s -o '-p %d -k %s'" % (
			os.path.join(self.parameters['postgres_binaries_path'], 'pg_ctl'),
			self.parameters['working_dir'],
			self.parameters['port'],
			self.parameters['working_dir']
		)

		subprocess.check_call(
			command_line,
			shell=True,
			stdout=self._eat_output(),
			stderr=self._eat_output()
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def is_running(self, keyword=None):
		command_line = [
			os.path.join(self.parameters['postgres_binaries_path'], 'pg_ctl'),
			'status',
			'-D',
			self.parameters['working_dir']
		]
		code = subprocess.call(
			command_line,
			stdout=self._eat_output(),
			stderr=self._eat_output()
		)
		return code == 0

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the Postgres server, allowing for it to be restarted later.
		"""
		command_line = [
			os.path.join(self.parameters['postgres_binaries_path'], 'pg_ctl'),
			'status',
			'-D',
			self.parameters['working_dir']
		]
		try:
			output = subprocess.check_output(command_line)
			# From the output, fetch the PID.
			pid = int(re.search('(\d+)', output).group(1))
			os.kill(pid, sig)
		except subprocess.CalledProcessError, ex:
			# It's not running. Do nothing.
			pass

	def destroy(self):
		"""
		Destroy this instance of Postgres, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class PostgresDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(PostgresDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(PostgresDaemonTest, self).tearDown()

	def test_basic(self):
		self.server = PostgresDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
			'/usr/lib/postgresql/9.1/bin', # TODO: Ubuntu Specific.
			self.configuration.get_free_port(),
			'127.0.0.1' # TODO: This doesn't work yet.
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Postgres server.")

		self.assertTrue(self.server.is_running())

		self.server.stop()

		# Give it a little time to stop.
		time.sleep(0.5)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Postgres server.")

		self.assertTrue(self.server.is_running())
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
import platform

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

	def configure(self, working_dir, postgres_binaries_path, port, bind_host, callback, error_callback, password=None):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg str postgres_binaries_path: The path to the binaries for Postgres.
		:arg int port: The port to listen on.
		:arg str bind_host: The address to bind to.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The error callback on error.
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

		def installed_db(code):
			if code == 0:
				# Success!
				self._fetch_output()
				self.save_parameters()

				callback("Successfully created Postgres database.")
			else:
				# Failed. Send back stdout/stderr.
				raw_output = self._fetch_output()
				error_callback("Failed to create Postgres database:\n" + raw_output)

		paasmaker.util.popen.Popen(
			command_line,
			on_stdout=self._fetchable_output,
			redirect_stderr=True,
			on_exit=installed_db,
			io_loop=self.configuration.io_loop,
		)

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

		paasmaker.util.popen.Popen(
			command_line,
			on_stdout=self._fetchable_output,
			redirect_stderr=True,
			io_loop=self.configuration.io_loop
		)

		def timeout(message):
			# Fetch the output and call the error callback.
			raw_output = self._fetch_output()
			error_callback("Failed to start:\n" + raw_output)

		logging.info("MySQL started, waiting for listening state.")
		self._wait_until_port_inuse(
			self.parameters['port'],
			callback,
			timeout
		)

	def is_running(self, keyword=None):
		# TODO: This isn't async, but none of the rest is Async. Fix this.
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

	def stop(self, callback, error_callback, sig=signal.SIGTERM):
		"""
		Stop this instance of the Postgres server, allowing for it to be restarted later.
		"""
		command_line = [
			os.path.join(self.parameters['postgres_binaries_path'], 'pg_ctl'),
			'status',
			'-D',
			self.parameters['working_dir']
		]

		def found_pid(code):
			if code == 0:
				output = self._fetch_output()
				pid = int(re.search('(\d+)', output).group(1))
				try:
					os.kill(pid, sig)
				except OSError, ex:
					# No such process. That's ok.
					# Continue.
					pass

				# Wait for the process to finish.
				self._wait_until_stopped(callback, error_callback)
			else:
				callback("Not running, no action taken.")

		paasmaker.util.popen.Popen(
			command_line,
			on_stdout=self._fetchable_output,
			redirect_stderr=True,
			on_exit=found_pid,
			io_loop=self.configuration.io_loop,
		)

	def destroy(self, callback, error_callback):
		"""
		Destroy this instance of Postgres, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		def stopped(message):
			shutil.rmtree(self.parameters['working_dir'])
			callback("Removed Postgres instance.")

		self.stop(stopped, error_callback, signal.SIGKILL)

class PostgresDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def _postgres_path(self):
		if platform.system() == 'Darwin':
			# Postgres binaries are in the path on OSX.
			return ""
		else:
			# TODO: This is Ubuntu specific.
			return "/usr/lib/postgresql/9.1/bin"

	def setUp(self):
		super(PostgresDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy(self.stop, self.stop)
			self.wait()
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(PostgresDaemonTest, self).tearDown()

	def test_basic(self):
		self.server = PostgresDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
			self._postgres_path(),
			self.configuration.get_free_port(),
			'127.0.0.1', # TODO: This doesn't work yet.
			self.stop,
			self.stop
		)
		result = self.wait()
		self.assertIn("Successfully", result, "Wrong message.")
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Postgres server.")

		self.assertTrue(self.server.is_running())

		self.server.stop(self.stop, self.stop)
		result = self.wait()

		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Postgres server.")

		self.assertTrue(self.server.is_running())

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
import tornadoredis

class ManagedPostgresError(ManagedDaemonError):
	pass

class ManagedPostgres(ManagedDaemon):
	# TODO: Don't hardcode this.
	PG_CTL = "/usr/lib/postgresql/9.1/bin/pg_ctl"
	INITDB = "/usr/lib/postgresql/9.1/bin/initdb"

	def _eat_output(self):
		return open("%s/%s" % (self.parameters['working_dir'], str(uuid.uuid4())), 'w')

	def configure(self, working_dir, port, bind_host, password=None):
		"""
		Configure this instance.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		self.parameters['password'] = password

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		# Now, we actually need to run pg_ctl initdb to get it all set up.
		command_line = "%s -D %s --username=postgres" % (
			self.INITDB,
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
			self.PG_CTL,
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
		command_line = [self.PG_CTL, 'status', '-D', self.parameters['working_dir']]
		code = subprocess.call(
			command_line,
			stdout=self._eat_output(),
			stderr=self._eat_output()
		)
		return code == 0

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the postgres server, allowing for it to be restarted later.
		"""
		command_line = [self.PG_CTL, 'status', '-D', self.parameters['working_dir']]
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
		Destroy this instance of postgres, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class ManagedPostgresTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ManagedPostgresTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(ManagedPostgresTest, self).tearDown()

	def test_basic(self):
		self.server = ManagedPostgres(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
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
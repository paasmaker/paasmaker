#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest

import paasmaker
from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado.testing
from paasmaker.thirdparty.tornadoredis import Client as TornadoRedisClient

class RedisDaemonError(ManagedDaemonError):
	pass

class RedisDaemon(ManagedDaemon):
	"""
	Start up a managed Redis daemon, for use by other service
	plugins, or in unit tests.

	As Redis doesn't really allow for multiple databases in the
	same instance, this class is an easy way to simulate that by
	starting a seperate instance per required database.

	Currently, it chooses some persistence options that match
	the default Ubuntu/Debian configuration. In future it will
	offer other canned persistence options to better suit
	what the server is being used for.
	"""

	REDIS_SERVER_CONFIG = """
daemonize yes
pidfile %(working_dir)s/redis.pid
dir %(working_dir)s
port %(port)d
bind %(host)s

databases 16

# Default set of save entries from Ubuntu/Debian.
save 900 1
save 300 10
save 60 10000

dbfilename %(working_dir)s/dump.rdb

# Optional password line.
%(auth_line)s

timeout 300
loglevel notice
logfile %(working_dir)s/redis.log
appendonly no
"""

	def configure(self, working_dir, port, bind_host, callback, error_callback, password=None):
		"""
		Configure this Redis instance.

		:arg str working_dir: The working directory to store files.
		:arg int port: The TCP port to listen on.
		:arg str bind_host: The IP address to bind to.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The error callback to call in case of error.
		:arg str|None password: If supplied, clients will require
			this password to connect to the daemon.
		"""
		# TODO: Allow a memory limit.
		# TODO: Allow custom configuration entries.
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		self.parameters['password'] = password

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		self.save_parameters()

		callback("Successfully configured Redis.")

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'redis.pid')

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		if not self.configuration.get_flat('redis_binary'):
			raise ValueError("Unable to find redis binary. It needs to be in the path, or manually configured in the configuration file.")

		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		if self.parameters['password']:
			self.parameters['auth_line'] = "requirepass %s" % self.parameters['password']
		else:
			self.parameters['auth_line'] = ''
		redisconfig = self.REDIS_SERVER_CONFIG % self.parameters
		fp = open(configfile, 'w')
		fp.write(redisconfig)
		fp.close()

		def process_forked(code):
			if code == 0:
				# Wait for the port to come into use.
				logging.info("Redis started, waiting for listening state.")
				self._wait_until_port_inuse(
					self.parameters['port'],
					callback,
					error_callback
				)
			else:
				error_message = "Unable to start Redis - exited with error code %d." % code
				error_message += "Output:\n" + self._fetch_output()
				logging.error(error_message)
				error_callback(error_message)

		# Fire up the server.
		logging.info("Starting up redis server on port %d." % self.parameters['port'])
		try:
			paasmaker.util.popen.Popen(
				[
					self.configuration.get_flat('redis_binary'),
					self.get_configuration_path(self.parameters['working_dir'])
				],
				redirect_stderr=True,
				on_stdout=self._fetchable_output,
				on_exit=process_forked,
				io_loop=self.configuration.io_loop
			)
		except OSError, ex:
			logging.error(ex)
			error_callback(str(ex), exception=ex)

	def get_client(self):
		"""
		Get a redis client object for this instance.

		CAUTION: This should only be used for unit tests. It
		returns a persistent connection that could cause some
		weird behaviour with production use.
		"""
		if self.client:
			return self.client

		# Create a client for it.
		self.client = TornadoRedisClient(
			host=self.parameters['host'],
			port=self.parameters['port'],
			io_loop=self.configuration.io_loop
		)
		self.client.connect()

		return self.client

	def is_running(self, keyword=None):
		return super(RedisDaemon, self).is_running('redis-server')

	def stop(self, callback, error_callback, sig=signal.SIGTERM):
		"""
		Stop this instance of the redis server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		super(RedisDaemon, self).stop(callback, error_callback, sig)

	def destroy(self, callback, error_callback):
		"""
		Destroy this instance of redis, removing all assigned data.
		"""
		def stopped(message):
			# Delete all the files.
			shutil.rmtree(self.parameters['working_dir'])
			callback(message)

		# Hard shutdown - we're about to delete the data anyway.
		self.stop(stopped, error_callback, signal.SIGKILL)

class RedisDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(RedisDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy(self.stop, self.stop)

		# Wait for destruction.
		self.wait()

		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(RedisDaemonTest, self).tearDown()

	def callback(self, channel, method, header, body):
		# Print out the message.
		#print body
		# Signal that we got it.
		self.stop()

	def test_basic(self):
		self.server = RedisDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('redis'),
			self.configuration.get_free_port(),
			'127.0.0.1',
			self.stop,
			self.stop
		)
		result = self.wait()

		self.assertIn("Success", result, "Did not configure correctly.")

		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Redis server.")

		client = self.server.get_client()

		client.set('test', 'foo', callback=self.stop)
		self.wait()

		client.get('test', callback=self.stop)
		result = self.wait()

		self.assertEquals('foo', result, "Result was not as expected.")

		# Stop it and restart it.
		self.server.stop(self.stop, self.stop)
		result = self.wait()

		self.assertIn("finished", result, "Wrong return message.")

		self.server.start(self.stop, self.stop)

		result = self.wait()
		self.assertIn("In appropriate state", result, "Failed to start Redis server.")
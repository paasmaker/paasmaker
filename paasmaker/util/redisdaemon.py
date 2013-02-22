
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
import tornadoredis

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

dbfilename dump.rdb

# Optional password line.
%(auth_line)s

timeout 300
loglevel notice
logfile %(working_dir)s/redis.log
appendonly no
"""

	def configure(self, working_dir, port, bind_host, password=None):
		"""
		Configure this Redis instance.

		:arg str working_dir: The working directory to store files.
		:arg int port: The TCP port to listen on.
		:arg str bind_host: The IP address to bind to.
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

		# Fire up the server.
		logging.info("Starting up redis server on port %d." % self.parameters['port'])
		subprocess.check_call(
			[
				self.configuration.get_flat('redis_binary'),
				self.get_configuration_path(self.parameters['working_dir'])
			]
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

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
		self.client = tornadoredis.Client(
			host=self.parameters['host'],
			port=self.parameters['port'],
			io_loop=self.configuration.io_loop
		)
		self.client.connect()

		return self.client

	def is_running(self, keyword=None):
		return super(RedisDaemon, self).is_running('redis-server')

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the redis server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		super(RedisDaemon, self).stop(sig)

	def destroy(self):
		"""
		Destroy this instance of redis, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class RedisDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(RedisDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
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
			'127.0.0.1'
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start Redis server.")

		client = self.server.get_client()

		client.set('test', 'foo', callback=self.stop)
		self.wait()

		client.get('test', callback=self.stop)
		result = self.wait()

		self.assertEquals('foo', result, "Result was not as expected.")

		# TODO: Test stopping and resuming the service.
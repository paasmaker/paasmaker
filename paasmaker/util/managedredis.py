
import tornadoredis
import os
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest

from manageddaemon import ManagedDaemon, ManagedDaemonError

class ManagedRedisError(ManagedDaemonError):
	pass

class ManagedRedis(ManagedDaemon):
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
vm-enabled no
"""

	def configure(self, working_dir, port, bind_host, password=None):
		"""
		Configure this instance.
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

	def start(self):
		"""
		Start up the server for this instance.

		Throws an exception if the redis server fails to start.
		"""
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

	def get_client(self, io_loop=None):
		"""
		Get a redis client object for this instance.
		"""
		if self.client:
			return self.client

		# Create a client for it.
		self.client = tornadoredis.Client(host=self.parameters['host'],
			port=self.parameters['port'], io_loop=io_loop)
		self.client.connect()

		return self.client

	def is_running(self, keyword=None):
		return super(ManagedRedis, self).is_running('redis-server')

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the redis server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		super(ManagedRedis, self).stop(sig)

	def destroy(self):
		"""
		Destroy this instance of redis, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

# TODO: Add unit tests for this.
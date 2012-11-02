
import tornadoredis
import os
import signal
import shutil
import tempfile
import logging
import subprocess
import json
import time

class ManagedRedisError(Exception):
	pass

class ManagedRedis(object):
	redis_server_config = """
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

timeout 300
loglevel notice
logfile %(working_dir)s/redis.log
appendonly no
vm-enabled no
"""

	def __init__(self, configuration):
		self.configuration = configuration
		self.parameters = {}
		self.client = None

	def configure(self, working_dir, port, bind_host):
		"""
		Configure this instance.
		"""
		# TODO: Allow setting a password.
		# TODO: Allow a memory limit.
		# TODO: Allow custom configuration entries.
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port
		self.parameters['host'] = bind_host

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		self.save_parameters()

	def load_parameters(self, working_dir):
		"""
		Load the parameters from the working directory.

		Throws an exception if that directory is not configured.
		"""
		parameters_path = self.get_parameters_path(working_dir)
		if os.path.exists(config_path):
			# TODO: Some more error checking.
			fp = open(config_path, 'r')
			self.parameters = json.loads(fp.read())
			fp.close()
		else:
			raise ManagedRedisError('No configuration file found in the working directory. Looking for %s.' % config_path)

	def save_parameters(self):
		"""
		Save the parameters file to disk.
		"""
		# TODO: More error checking.
		fp = open(self.get_parameters_path(self.parameters['working_dir']), 'w')
		fp.write(json.dumps(self.parameters))
		fp.close()

	def get_parameters_path(self, working_dir):
		"""
		Get the parameters configuration path.
		"""
		return os.path.join(working_dir, 'redis.json')

	def get_configuration_path(self, working_dir):
		"""
		Get the redis server configuration path.
		"""
		return os.path.join(working_dir, 'redis.conf')

	def get_pid(self):
		"""
		Gets the PID of the running instance. This just reads the on disk
		PID file, and may not as such indicate that it's running. Returns
		None if no pid file found.
		"""
		pidpath = os.path.join(self.parameters['working_dir'], 'redis.pid')
		if os.path.exists(pidpath):
			fp = open(pidpath, 'r')
			pid = int(fp.read())
			fp.close()
			return pid
		else:
			return None

	def start(self):
		"""
		Start up the server for this instance.

		Throws an exception if the redis server fails to start.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		redisconfig = self.redis_server_config % self.parameters
		fp = open(configfile, 'w')
		fp.write(redisconfig)
		fp.close()

		# Fire up the server.
		logging.info("Starting up redis server on port %d." % self.parameters['port'])
		subprocess.check_call([self.configuration.get_flat('redis_binary'), self.get_configuration_path(self.parameters['working_dir'])])

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

	def stop(self):
		"""
		Stop this instance of the redis server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		pid = self.get_pid()
		if pid:
			os.kill(pid, signal.SIGTERM)

	def destroy(self):
		"""
		Destroy this instance of redis, removing all assigned data.
		"""
		self.stop()
		# TODO: This blocks the process. It's required because if we
		# remove the dir too soon, it doesn't end up killing the redis process.
		time.sleep(0.2)
		shutil.rmtree(self.parameters['working_dir'])
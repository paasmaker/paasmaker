
import paasmaker
import tornadoredis
import os
import signal
import shutil
import tempfile
import logging
import subprocess

class MemoryRedis:
	# TODO: too specific to the server setup.
	redis_binary_path = "/usr/bin/redis-server"
	redis_server_config = """
daemonize yes
pidfile %(pidfile)s
dir %(dir)s
port %(port)d
bind %(host)s

databases 16

# No save commands - so in memory only.

timeout 300
loglevel notice
logfile stdout
appendonly no
vm-enabled no
"""

	def __init__(self, configuration):
		self.started = False
		self.configuration = configuration
		self.client = None

	def started(self):
		return self.started

	def start(self):
		# Choose some configuration values.
		self.port = self.configuration.get_free_port()
		self.host = "127.0.0.1"
		self.configfile = tempfile.mkstemp()[1]
		self.dir = tempfile.mkdtemp()
		self.pidfile = os.path.join(self.dir, 'redis.pid')

		# Write out the configuration.
		values = {'pidfile': self.pidfile, 'port': self.port, 'host': self.host, 'dir': self.dir}
		redisconfig = self.redis_server_config % values
		open(self.configfile, 'w').write(redisconfig)

		# Fire up the server.
		logging.info("Starting up redis server because requested by test.")
		subprocess.check_call([self.redis_binary_path, self.configfile])

		self.started = True

	def get_client(self, io_loop=None):
		if self.client:
			return self.client

		# Create a client for it.
		self.client = tornadoredis.Client(host=self.host, port=self.port,
			io_loop=io_loop)
		self.client.connect()

		return self.client

	def stop(self):
		if self.started:
			if self.client:
				self.client.disconnect()
			# Clean up the redis.
			redispid = int(open(self.pidfile, 'r').read())
			os.kill(redispid, signal.SIGTERM)
			os.unlink(self.configfile)
			shutil.rmtree(self.dir)
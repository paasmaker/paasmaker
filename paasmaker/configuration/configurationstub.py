import unittest
import os
import signal
import logging
import tempfile
import uuid
import shutil
import hashlib
import logging
import subprocess
import configuration

import tornadoredis

class ConfigurationStub(configuration.Configuration):
	"""A test version of the configuration object, for unit tests."""
	default_config = """
auth_token: %(auth_token)s
log_directory: %(log_dir)s
"""

	pacemaker_config = """
pacemaker:
  enabled: true
  dsn: "sqlite:///:memory:"
"""

	heart_config = """
heart:
  enabled: true
  working_dir: %(heart_working_dir)s
  runtimes:
    - name: php
      cls: path.to.class
      language: PHP
      versions:
        - 5.3
        - 5.4
    - name: ruby
      cls: path.to.class
      language: Ruby
      versions:
        - 1.8.7
        - 1.9.3
"""

	router_config = """
router:
  enabled: true
  redis: %(redis)s
"""

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

	def __init__(self, modules=[]):
		# Choose filenames and set up example configuration.
		configfile = tempfile.mkstemp()
		self.params = {}

		self.params['log_dir'] = tempfile.mkdtemp()
		self.params['auth_token'] = str(uuid.uuid4())
		self.params['heart_working_dir'] = tempfile.mkdtemp()

		# Create the configuration file.
		configuration = self.default_config % self.params

		if 'pacemaker' in modules:
			configuration += self.pacemaker_config % self.params
		if 'heart' in modules:
			configuration += self.heart_config % self.params
		if 'router' in modules:
			configuration += self.router_config % self.params

		self.configname = configfile[1]
		open(self.configname, 'w').write(configuration)

		self.redis = None

		# Call parent constructor.
		super(ConfigurationStub, self).__init__()
		# And then load the config.
		super(ConfigurationStub, self).load_from_file([self.configname])

		# And if we're a pacemaker, create the DB.
		if 'pacemaker' in modules:
			self.setup_database()

	def get_redis(self, testcase=None):
		if not self.redis:
			if not testcase:
				# This is to remain API compatible with the original configuration object.
				raise ValueError("You must call get_redis the first time with a testcase argument, to initialize it.")
			# Choose some configuration values.
			self.redis = {}
			self.redis['port'] = self.get_free_port()
			self.redis['host'] = "127.0.0.1"
			self.redis['configfile'] = tempfile.mkstemp()[1]
			self.redis['dir'] = tempfile.mkdtemp()
			self.redis['pidfile'] = os.path.join(self.redis['dir'], 'redis.pid')
			self.redis['testcase'] = testcase

			# Write out the configuration.
			redisconfig = self.redis_server_config % self.redis
			open(self.redis['configfile'], 'w').write(redisconfig)

			# Fire up the server.
			logging.info("Starting up redis server because requested by test.")
			subprocess.check_call([self.redis_binary_path, self.redis['configfile']])

			# Wait for it to start up.
			testcase.short_wait_hack()

			# Create a client for it.
			client = tornadoredis.Client(host=self.redis['host'], port=self.redis['port'],
				io_loop=testcase.io_loop)
			client.connect()
			self.redis['client'] = client

		# Clear all keys before returning the client.
		self.redis['client'].flushall(callback=self.redis['testcase'].stop)
		self.redis['testcase'].wait()

		return self.redis['client']

	def get_redis_configuration(self):
		if not self.redis:
			raise Exception("Redis not initialized.")
		return self.redis

	def cleanup(self):
		# Remove files that we created.
		shutil.rmtree(self.params['log_dir'])
		shutil.rmtree(self.params['heart_working_dir'])
		os.unlink(self.configname)

		if self.redis:
			self.redis['client'].disconnect()
			# Clean up the redis.
			redispid = int(open(self.redis['pidfile'], 'r').read())
			os.kill(redispid, signal.SIGTERM)
			os.unlink(self.redis['configfile'])
			shutil.rmtree(self.redis['dir'])

	def get_tornado_configuration(self):
		settings = super(ConfigurationStub, self).get_tornado_configuration()
		# Force debug mode on.
		settings['debug'] = True
		return settings

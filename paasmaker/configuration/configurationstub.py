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
import paasmaker

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

			self.redis = paasmaker.util.memoryredis.MemoryRedis(self)
			self.redis.start()

			# Wait for it to start up.
			testcase.short_wait_hack()

			self.client = self.redis.get_client(io_loop=testcase.io_loop)

		return self.client

	def get_redis_object(self):
		if not self.redis:
			raise Exception("Redis not initialized.")
		return self.redis

	def cleanup(self):
		# Remove files that we created.
		shutil.rmtree(self.params['log_dir'])
		shutil.rmtree(self.params['heart_working_dir'])
		os.unlink(self.configname)

		if self.redis:
			self.redis.stop()

	def get_tornado_configuration(self):
		settings = super(ConfigurationStub, self).get_tornado_configuration()
		# Force debug mode on.
		settings['debug'] = True
		return settings

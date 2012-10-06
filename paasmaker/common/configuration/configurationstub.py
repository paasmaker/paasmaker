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
import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ConfigurationStub(configuration.Configuration):
	"""A test version of the configuration object, for unit tests."""
	default_config = """
# The port to this test instance is the master port, for testing purposes.
http_port: %(master_port)d
auth_token: %(auth_token)s
log_directory: %(log_dir)s
scratch_directory: %(scratch_dir)s
master_host: localhost
master_port: %(master_port)d
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
    - name: paasmaker.runtime.php
      cls: paasmaker.heart.runtime.PHPRuntime
      title: PHP
      versions:
        - 5.3
        - 5.4
      parameters:
        apache_config_dir: /tmp/foo
    #- name: paasmaker.runtime.ruby
    #  cls: paasmaker.heart.runtime.RubyRuntime
    #  title: Ruby
    #  versions:
    #    - 1.8.7
    #    - 1.9.3
    #  parameters:
    #    foo: bar
    #    baz: bar
"""

	router_config = """
router:
  enabled: true
  redis:
    master:
      host: localhost
      port: 6379
    local:
      host: localhost
      port: 6379
"""

	def __init__(self, port=8888, modules=[]):
		# Choose filenames and set up example configuration.
		configfile = tempfile.mkstemp()
		self.params = {}

		self.params['log_dir'] = tempfile.mkdtemp()
		self.params['auth_token'] = str(uuid.uuid4())
		self.params['heart_working_dir'] = tempfile.mkdtemp()
		self.params['scratch_dir'] = tempfile.mkdtemp()
		self.params['master_port'] = port

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

		self.router_redis = None
		self.message_broker_server = None
		self.message_broker_client = None

		# Call parent constructor.
		super(ConfigurationStub, self).__init__()
		# And then load the config.
		super(ConfigurationStub, self).load_from_file([self.configname])

		# Choose a UUID for ourself.
		#self.set_node_uuid(str(uuid.uuid4()))

		# And if we're a pacemaker, create the DB.
		if 'pacemaker' in modules:
			self.setup_database()

	def get_router_redis(self, testcase=None):
		if not self.router_redis:
			if not testcase:
				# This is to remain API compatible with the original configuration object.
				raise ValueError("You must call the first time with a testcase argument, to initialize it.")

			self.router_redis = paasmaker.util.memoryredis.MemoryRedis(self)
			self.router_redis.start()

			# Wait for it to start up.
			testcase.short_wait_hack()

			self.router_redis_client = self.router_redis.get_client(io_loop=testcase.io_loop)

		return self.router_redis_client

	def get_router_redis_object(self):
		if not self.router_redis:
			raise Exception("Router redis not initialized.")
		return self.router_redis

	def cleanup(self):
		# Remove files that we created.
		shutil.rmtree(self.params['log_dir'])
		shutil.rmtree(self.params['heart_working_dir'])
		shutil.rmtree(self.params['scratch_dir'])
		os.unlink(self.configname)

		if self.router_redis:
			self.router_redis.stop()
		if self.message_broker_server:
			self.message_broker_server.stop()

	def get_tornado_configuration(self):
		settings = super(ConfigurationStub, self).get_tornado_configuration()
		# Force debug mode on.
		settings['debug'] = True
		return settings

	def setup_message_exchange(self, status_ready_callback=None, audit_ready_callback=None, io_loop=None):
		self.exchange = paasmaker.common.core.MessageExchange(self)
		if not self.message_broker_server:
			logger.debug("Firing up temporary rabbitmq server... (this can take a few seconds)")

			# A callback that finishes the setup.
			def on_connection_ready(client):
				logger.debug("Temporary rabbitmq server is running. Setting up exchange.")
				self.exchange.setup(client, status_ready_callback, audit_ready_callback)

			# Start up a message broker.
			self.message_broker_server = paasmaker.util.temporaryrabbitmq.TemporaryRabbitMQ(self)
			self.message_broker_server.start()
			self.message_broker_server.get_client(io_loop=io_loop, callback=on_connection_ready)
		else:
			# Already fired up. Just call the callbacks.
			if status_ready_callback:
				status_ready_callback()
			if audit_ready_callback:
				audit_ready_callback()

class TestConfigurationStub(unittest.TestCase):
	def test_simple(self):
		stub = ConfigurationStub(modules=['pacemaker', 'heart', 'router'])
		# And I guess we shouldn't have any exceptions...

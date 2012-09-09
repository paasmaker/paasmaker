# General imports.
import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationException
from paasmaker.util.configurationhelper import NoConfigurationFileException
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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import colander

# For parsing command line options.
from tornado.options import define, options
import tornado.testing

import tornadoredis

# Set up logging for this module.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Set up command line options.
define("debug", type=int, default=0, help="Enable Tornado debug mode.")

# The Configuration Schema.
class PacemakerSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Pacemaker enabled",
		description="Pacemaker is enabled for this node",
		missing=False,
		default=False)

	dsn = colander.SchemaNode(colander.String(),
		title="Database DSN",
		description="Database connection details for this pacemaker, in SQLAlchemy format")

	login_age = colander.SchemaNode(colander.Integer(),
		title="Login age",
		description="The number of days to grant access when logging in, before requiring a new login.",
		default=7,
		missing=7)

	@staticmethod
	def default():
		return {'enabled': False}

class HeartRuntimeSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Symbolic name",
		description="The symbolic name for this runtime, used to match it up in application configuration")
	cls = colander.SchemaNode(colander.String(),
		title="Runtime Class",
		description="The class used to provide this runtime")
	language = colander.SchemaNode(colander.String(),
		title="Friendly name",
		description="The friendly name for this runtime")
	versions = colander.SchemaNode(colander.Sequence(),
		colander.SchemaNode(colander.String(),
		title="Versions",
		description="List of versions that are supported"))

class HeartRuntimesSchema(colander.SequenceSchema):
	runtime = HeartRuntimeSchema()

class HeartSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Heart enabled",
		description="Heart is enabled for this node",
		missing=False,
		default=False)

	working_dir = colander.SchemaNode(colander.String(),
		title="Working directory",
		description="Directory where heart working files are stored")

	runtimes = HeartRuntimesSchema(
		title="Runtimes",
		description="A list of runtimes offered by this heart",
		missing=[],
		default=[])

	@staticmethod
	def default():
		return {'enabled': False, 'runtimes': []}

class RouterSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Router enabled",
		description="Router is enabled for this node",
		missing=False,
		default=False)

	redis = colander.SchemaNode(colander.String(),
		title="Redis connection string",
		description="The redis connection string. CAUTION: Do NOT share redis instances with other routers.")

	@staticmethod
	def default():
		return {'enabled': False}

class ConfigurationSchema(colander.MappingSchema):
	http_port = colander.SchemaNode(colander.Integer(),
		title="HTTP Port",
		description="The HTTP port that this node listens on for API requests",
		missing=8888,
		default=8888)
	
	my_route = colander.SchemaNode(colander.String(),
		title="Route to this node",
		description="The route (IP address or Hostname) that should be used to contact this host. If not specified, it will be automatically determined",
		missing=None,
		default=None)

	auth_token = colander.SchemaNode(colander.String(),
		title="Authentication Token",
		description="Token used by nodes to validate each other. All nodes should have the same token")

	log_directory = colander.SchemaNode(colander.String(),
		title="Log Directory",
		description="Directory used to store log files",
		default="/tmp/paasmaker-logs/", # TODO: use a better temp dir.
		missing="/tmp/paasmaker-logs/")

	server_log_level = colander.SchemaNode(colander.String(),
		title="Server log level",
		description="The log level for the server log file.",
		default="INFO",
		missing="INFO")

	pacemaker = PacemakerSchema(default=PacemakerSchema.default(),missing=PacemakerSchema.default())
	heart = HeartSchema(defalt=HeartSchema.default(),missing=HeartSchema.default())
	router = RouterSchema(default=RouterSchema.default(),missing=RouterSchema.default())

class ImNotA(Exception):
	pass

class Configuration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self):
		super(Configuration, self).__init__(ConfigurationSchema())

	def is_pacemaker(self):
		return self.get_flat('pacemaker.enabled')
	def is_heart(self):
		return self.get_flat('heart.enabled')
	def is_router(self):
		return self.get_flat('router.enabled')

	def setup_database(self):
		if not self.is_pacemaker():
			raise ImNotA("I'm not a pacemaker.")

		# Connect.
		self.engine = create_engine(self.get_flat('pacemaker.dsn'))
		self.session = sessionmaker(bind=self.engine)

		# Create the tables.
		paasmaker.model.Base.metadata.bind = self.engine
		paasmaker.model.Base.metadata.create_all()

	def get_database_session(self):
		"""
		Get a database session object. Each requesthandler should fetch
		one of these when it needs to, but hang onto it - repeated
		calls will fetch new sessions every time.
		"""
		if not self.is_pacemaker():
			raise ImNotA("I'm not a pacemaker.")
		return self.session()

	def get_redis(self):
		pass

	def get_tornado_configuration(self):
		settings = {}
		# TODO: Use a different value from the auth token?
		settings['cookie_secret'] = self['auth_token']
		settings['template_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../templates')
		settings['static_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../static')
		settings['debug'] = (options.debug == 1)
		settings['xheaders'] = True
		return settings

	def get_job_logger(self, job_id):
		return paasmaker.util.joblogging.JobLoggerAdapter(logging.getLogger('job'), job_id, self)
	def get_job_log_path(self, job_id):
		container = os.path.join(self['log_directory'], 'job')
		checksum = hashlib.md5()
		checksum.update(job_id)
		checksum = checksum.hexdigest()
		container = os.path.join(container, checksum[0:4])
		if not os.path.exists(container):
			os.makedirs(container)
		path = os.path.join(container, checksum + '.log')
		return path
	def get_job_pub_topic(self, job_id):
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'message', 'j' + job_id)
	def job_exists_locally(self, job_id):
		path = self.get_job_log_path(job_id)
		return os.path.exists(path)

class ConfigurationStub(Configuration):
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
			self.redis['port'] = tornado.testing.get_unused_port()
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

class TestConfiguration(unittest.TestCase):
	minimum_config = """
auth_token: 5893b415-f166-41a8-b606-7bdb68b88f0b
"""
	
	def setUp(self):
		self.tempnam = tempfile.mkstemp()[1]

	def tearDown(self):
		if os.path.exists(self.tempnam):
			os.unlink(self.tempnam)

	def test_fail_load(self):
		try:
			config = Configuration()
			config.load_from_file(['test_failure.yml'])
			self.assertTrue(False, "Should have thrown NoConfigurationFileException exception.")
		except NoConfigurationFileException, ex:
			self.assertTrue(True, "Threw exception correctly.")

		try:
			open(self.tempnam, 'w').write("test:\n  foo: 10")
			config = Configuration()
			config.load_from_file([self.tempnam])
			self.assertTrue(False, "Configuration was considered valid, but it should not have been.")
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Configuration did not pass the schema or was invalid.")

	def test_simple_default(self):
		open(self.tempnam, 'w').write(self.minimum_config)
		config = Configuration()
		config.load_from_file([self.tempnam])
		self.assertEqual(config.get_flat('http_port'), 8888, 'No default present.')
	
	def test_heart_languages(self):
		# TODO: Complete this.
		stub = ConfigurationStub(modules=['heart'])


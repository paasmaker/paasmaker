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

class MiscPortsSchema(colander.MappingSchema):
	minimum = colander.SchemaNode(colander.Integer(),
		title="Minimum port",
		description="Lower end of the port range to search for free ports on.",
		missing=10100,
		default=10100)
	maximum = colander.SchemaNode(colander.Integer(),
		title="Maximum port",
		description="Upper end of the port range to search for free ports on.",
		missing=10500,
		default=10500)
	
	@staticmethod
	def default():
		return {'minimum': 10100, 'maximum': 10500}

class ConfigurationSchema(colander.MappingSchema):
	http_port = colander.SchemaNode(colander.Integer(),
		title="HTTP Port",
		description="The HTTP port that this node listens on for API requests",
		missing=8888,
		default=8888)

	misc_ports = MiscPortsSchema(default=MiscPortsSchema.default(),missing=MiscPortsSchema.default())
	
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
		self.port_allocator = paasmaker.util.port.FreePortFinder()

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
	
	def get_free_port(self):
		return self.port_allocator.free_in_range(self.get_flat('misc_ports.minimum'), self.get_flat('misc_ports.maximum'))

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


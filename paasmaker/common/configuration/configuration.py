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
import socket

from pubsub import pub

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import colander

# For parsing command line options.
from tornado.options import define, options
import tornado.testing

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
	title = colander.SchemaNode(colander.String(),
		title="Friendly name",
		description="The friendly name for this runtime")
	versions = colander.SchemaNode(colander.Sequence(),
		colander.SchemaNode(colander.String(),
		title="Versions",
		description="List of versions that are supported"))
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Runtime Parameters",
		description="Parameters for this particular runtime",
		missing={},
		default={})

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

class RedisConnectionSchema(colander.MappingSchema):
	host = colander.SchemaNode(colander.String(),
		title="Hostname",
		description="Redis Hostname")
	port = colander.SchemaNode(colander.Integer(),
		title="Port",
		description="Redis Port")
	password = colander.SchemaNode(colander.String(),
		title="Password",
		description="Redis Password",
		missing="",
		default="")

class RouterRedisSchema(colander.MappingSchema):
	master = RedisConnectionSchema()
	local = RedisConnectionSchema()

class RouterSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Router enabled",
		description="Router is enabled for this node",
		missing=False,
		default=False)

	redis = RouterRedisSchema()

	@staticmethod
	def default():
		redis_default = {
			'master': {'host':'localhost', 'port':6379},
			'local': {'host':'localhost', 'port':6379}
		}
		return {'enabled': False, 'redis': redis_default}

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

class MessageBrokerSchema(colander.MappingSchema):
	hostname = colander.SchemaNode(colander.String(),
		title="Hostname",
		description="Hostname of the message broker.")
	port = colander.SchemaNode(colander.Integer(),
		title="Port",
		description="The port of the message broker.")
	username = colander.SchemaNode(colander.String(),
		title="Username",
		description="The username to connect as.",
		default="guest",
		missing="guest")
	password = colander.SchemaNode(colander.String(),
		title="Password",
		description="The password to connect as.",
		default="guest",
		missing="guest")
	virtualhost = colander.SchemaNode(colander.String(),
		title="Virtual Host",
		description="The virtual host to connect to.",
		default="/",
		missing="/")

	@staticmethod
	def default():
		return {'hostname': 'localhost', 'port': 5672, 'username': 'guest', 'password': 'guest', 'virtualhost': '/'}

class ConfigurationSchema(colander.MappingSchema):
	http_port = colander.SchemaNode(colander.Integer(),
		title="HTTP Port",
		description="The HTTP port that this node listens on for API requests",
		missing=8888,
		default=8888)

	misc_ports = MiscPortsSchema(default=MiscPortsSchema.default(),missing=MiscPortsSchema.default())

	my_name = colander.SchemaNode(colander.String(),
		title="Node name",
		description="Friendly node name, or if not supplied, will attempt to detect the hostname.",
		missing=None,
		default=None)

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
		description="Directory used to store log files")

	server_log_level = colander.SchemaNode(colander.String(),
		title="Server log level",
		description="The log level for the server log file.",
		default="INFO",
		missing="INFO")

	scratch_directory = colander.SchemaNode(colander.String(),
		title="Scratch Directory",
		description="Directory used for random temporary files. Should be somewhere persistent between reboots, eg, not /tmp.")

	master_host = colander.SchemaNode(colander.String(),
		title="Master Node",
		description="The master node for this cluster.")
	master_port = colander.SchemaNode(colander.Integer(),
		title="Master Node HTTP port",
		description="The master node HTTP port for API requests.",
		default=8888,
		missing=8888)

	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes.",
		missing={},
		default={})

	broker = MessageBrokerSchema(default=MessageBrokerSchema.default(),missing=MessageBrokerSchema.default())

	pacemaker = PacemakerSchema(default=PacemakerSchema.default(),missing=PacemakerSchema.default())
	heart = HeartSchema(defalt=HeartSchema.default(),missing=HeartSchema.default())
	router = RouterSchema(default=RouterSchema.default(),missing=RouterSchema.default())

class ImNotA(Exception):
	pass

class Configuration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self):
		super(Configuration, self).__init__(ConfigurationSchema())
		self.port_allocator = paasmaker.util.port.FreePortFinder()
		self.plugins = paasmaker.util.PluginRegistry(self)
		self.uuid = None
		self.exchange = None

	def post_load(self):
		# Make sure directories exist.
		if not os.path.exists(self.get_flat('scratch_directory')):
			raise InvalidConfigurationException("Scratch directory does not exist.")
		if not os.path.exists(self.get_flat('log_directory')):
			raise InvalidConfigurationException("Log directory does not exist.")

		if self['my_name'] is None:
			self['my_name'] = os.uname()[1]
		if self['my_route'] is None:
			# TODO: improve this detection and use.
			self['my_route'] = socket.getfqdn()

		# Load heart plugins.
		if self.is_heart():
			self.load_plugins(self.plugins, self['heart']['runtimes'])

		self.update_flat()

	def is_pacemaker(self):
		return self.get_flat('pacemaker.enabled')
	def is_heart(self):
		return self.get_flat('heart.enabled')
	def is_router(self):
		return self.get_flat('router.enabled')

	def get_runtime_tags(self):
		if not self.is_heart():
			raise ImNotA("I'm not a heart, so I have no runtimes.")

		tags = {}
		for meta in self['heart']['runtimes']:
			tags[meta['name']] = True

		return tags

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

	def get_router_redis(self):
		# TODO: Implement!
		pass

	def setup_message_exchange(self, status_ready_callback=None, audit_ready_callback=None, io_loop=None):
		"""
		Set up the message broker connection and appropriate exchange.
		"""
		# TODO: Implement.
		pass

	def get_tornado_configuration(self):
		settings = {}
		# TODO: Use a different value from the auth token?
		settings['cookie_secret'] = self['auth_token']
		settings['template_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../templates')
		settings['static_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../../static')
		settings['debug'] = (options.debug == 1)
		settings['xheaders'] = True
		return settings

	def get_scratch_path(self, filename):
		return os.path.join(self.get_flat('scratch_directory'), filename)

	def get_supervisor_path(self):
		return os.path.normpath(os.path.dirname(__file__) + '/../../../supervisor.py')

	#
	# JOB HELPERS
	#
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
	def get_job_message_pub_topic(self, job_id):
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'message', 'j' + job_id)
	def get_job_status_pub_topic(self, job_id):
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'status', 'j' + job_id)
	def get_job_audit_pub_topic(self, job_id):
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'audit', 'j' + job_id)
	def job_exists_locally(self, job_id):
		path = self.get_job_log_path(job_id)
		return os.path.exists(path)
	def send_job_status(self, job_id, state, source=None):
		"""
		Propagate the status of a job to listeners who care inside our
		instance, and also likely down the Rabbit hole to other listeners.
		(Rabbit hole means RabbitMQ... so there is no confusion.)
		"""
		topic = self.get_job_status_pub_topic(job_id)

		# If source is not supplied, send along our own UUID.
		send_source = source
		if not send_source:
			send_source = self.get_node_uuid()

		pub.sendMessage(topic, job_id=job_id, state=state, source=send_source)
	def send_job_complete(self, job_id, state, summary, source=None):
		"""
		Send that a job is complete, with the given summary message.
		"""
		topic = self.get_job_audit_pub_topic(job_id)

		# If source is not supplied, send along our own UUID.
		send_source = source
		if not send_source:
			send_source = self.get_node_uuid()

		pub.sendMessage(topic, job_id=job_id, state=state, summary=summary, source=send_source)

	#
	# IDENTITY HELPERS
	#
	def set_node_uuid(self, uuid):
		"""
		Save our UUID to the scratch directory.
		"""
		path = os.path.join(self.get_flat('scratch_directory'), 'UUID')
		fp = open(path, 'w')
		fp.write(uuid)
		fp.close()
		# And save us loading it again later...
		self.uuid = uuid

	def get_node_uuid(self):
		"""
		Get our UUID, returning it from cache if we can.
		"""
		# Have we already loaded it? If so, return that.
		if self.uuid:
			return self.uuid
		# Try to open it.
		path = os.path.join(self.get_flat('scratch_directory'), 'UUID')
		if os.path.exists(path):
			# It exists. Read and return.
			fp = open(path, 'r')
			uuid = fp.read()
			fp.close()
			self.uuid = uuid
		else:
			# Doesn't exist. Return None, callers should handle this.
			pass

		return self.uuid

class TestConfiguration(unittest.TestCase):
	minimum_config = """
auth_token: 5893b415-f166-41a8-b606-7bdb68b88f0b
log_directory: /tmp
scratch_directory: /tmp
master_host: localhost
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


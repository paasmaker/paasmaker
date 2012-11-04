# General imports.
import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationException
from paasmaker.util.configurationhelper import NoConfigurationFileException
from paasmaker.common.core import constants
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
define("configfile", type=str, default="", help="Override configuration file.")

# Default ports.
DEFAULT_API_PORT = 42500

DEFAULT_ROUTER_REDIS_MASTER = 42510
DEFAULT_ROUTER_REDIS_SLAVE = 42511
DEFAULT_ROUTER_REDIS_STATS = 42512

DEFAULT_APPLICATION_MIN = 42600
DEFAULT_APPLICATION_MAX = 42699

# The Configuration Schema.
class PluginSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Symbolic name",
		description="The symbolic name for this plugin, used to match it up in application configuration")
	klass = colander.SchemaNode(colander.String(),
		name="class",
		title="Plugin class",
		description="The class used to provide this plugin")
	title = colander.SchemaNode(colander.String(),
		title="Friendly name",
		description="The friendly name for this plugin")
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Plugin Parameters",
		description="Parameters for this particular plugin",
		missing={},
		default={})

class PluginsSchema(colander.SequenceSchema):
	plugin = PluginSchema()

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

	plugins = PluginsSchema(
		title="Plugins",
		description="A list of plugins registered on this pacemaker.",
		missing=[],
		default=[])

	@staticmethod
	def default():
		return {'enabled': False, 'plugins': []}

class HeartSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Heart enabled",
		description="Heart is enabled for this node",
		missing=False,
		default=False)

	working_dir = colander.SchemaNode(colander.String(),
		title="Working directory",
		description="Directory where heart working files are stored")

	plugins = PluginsSchema(
		title="Plugins",
		description="A list of plugins registered on this heart.",
		missing=[],
		default=[])

	@staticmethod
	def default():
		return {'enabled': False, 'plugins': []}

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
		missing=None,
		default=None)
	managed = colander.SchemaNode(colander.Boolean(),
		title="Managed",
		description="If true, this is a managed redis instance. Paasmaker will create it on demand and manage storing it's data.",
		default=False,
		missing=False)

	@staticmethod
	def default_router_table():
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_MASTER, 'managed': False}
	@staticmethod
	def default_router_stats():
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_STATS, 'managed': False}

class RedisConnectionSlaveSchema(RedisConnectionSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Enable automatic slaving",
		description="Enable automatic slaving of this router table to the supplied values.",
		missing=False,
		default=False)

	@staticmethod
	def default():
		return {'enabled': False}

class RouterSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Router enabled",
		description="Router is enabled for this node",
		missing=False,
		default=False)

	table = RedisConnectionSchema(default=RedisConnectionSchema.default_router_table(), missing=RedisConnectionSchema.default_router_table())
	stats = RedisConnectionSchema(default=RedisConnectionSchema.default_router_stats(), missing=RedisConnectionSchema.default_router_stats())
	slaveof = RedisConnectionSlaveSchema(default=RedisConnectionSlaveSchema.default(), missing=RedisConnectionSlaveSchema.default())

	@staticmethod
	def default():
		return {
			'enabled': False,
			'table': RedisConnectionSchema.default_router_table(),
			'stats': RedisConnectionSchema.default_router_stats(),
			'slaveof': RedisConnectionSlaveSchema.default()
		}

class MiscPortsSchema(colander.MappingSchema):
	minimum = colander.SchemaNode(colander.Integer(),
		title="Minimum port",
		description="Lower end of the port range to search for free ports on.",
		missing=DEFAULT_APPLICATION_MIN,
		default=DEFAULT_APPLICATION_MIN)
	maximum = colander.SchemaNode(colander.Integer(),
		title="Maximum port",
		description="Upper end of the port range to search for free ports on.",
		missing=DEFAULT_APPLICATION_MAX,
		default=DEFAULT_APPLICATION_MAX)

	@staticmethod
	def default():
		return {'minimum': DEFAULT_APPLICATION_MIN, 'maximum': DEFAULT_APPLICATION_MAX}

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

class MasterSchema(colander.MappingSchema):
	host = colander.SchemaNode(colander.String(),
		title="Master Node",
		description="The master node for this cluster.")
	port = colander.SchemaNode(colander.Integer(),
		title="Master Node HTTP port",
		description="The master node HTTP port for API requests.",
		default=DEFAULT_API_PORT,
		missing=DEFAULT_API_PORT)
	isitme = colander.SchemaNode(colander.Boolean(),
		title="Am I the master?",
		description="If true, I'm the master node.",
		default=False,
		missing=False)

	@staticmethod
	def default():
		return {'host': 'localhost', 'port': DEFAULT_API_PORT, 'isitme': False}

class ConfigurationSchema(colander.MappingSchema):
	http_port = colander.SchemaNode(colander.Integer(),
		title="HTTP Port",
		description="The HTTP port that this node listens on for API requests",
		missing=DEFAULT_API_PORT,
		default=DEFAULT_API_PORT)

	misc_ports = MiscPortsSchema(default=MiscPortsSchema.default(), missing=MiscPortsSchema.default())

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

	master = MasterSchema(default=MasterSchema.default(), missing=MasterSchema.default())

	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes. Applications are passed these tags as well, so you will want to be careful what you put in here.",
		missing={},
		default={})

	broker = MessageBrokerSchema(default=MessageBrokerSchema.default(), missing=MessageBrokerSchema.default())

	pacemaker = PacemakerSchema(default=PacemakerSchema.default(), missing=PacemakerSchema.default())
	heart = HeartSchema(defalt=HeartSchema.default(), missing=HeartSchema.default())
	router = RouterSchema(default=RouterSchema.default(), missing=RouterSchema.default())

	# Server related configuration. This is for an Ubuntu server, set up as
	# per the installation instructions. Obviously, for other platforms
	# this will need to be altered.
	redis_binary = colander.SchemaNode(colander.String(),
		title="Redis server binary",
		description="The full path to the redis server binary.",
		default="/usr/bin/redis-server",
		missing="/usr/bin/redis-server")
	rabbitmq_binary = colander.SchemaNode(colander.String(),
		title="RabbitMQ server binary",
		description="The full path to the RabbitMQ server binary.",
		default="/usr/lib/rabbitmq/bin/rabbitmq-server",
		missing="/usr/lib/rabbitmq/bin/rabbitmq-server")
	nginx_binary =colander.SchemaNode(colander.String(),
		title="nginx server binary",
		description="The full path to the nginx server binary.",
		default="/usr/local/openresty/nginx/sbin/nginx",
		missing="/usr/local/openresty/nginx/sbin/nginx")

class ImNotA(Exception):
	pass

class ImNotAHeart(ImNotA):
	pass

class ImNotAPacemaker(ImNotA):
	pass

class ImNotARouter(ImNotA):
	pass

class JobStatusMessage(object):
	def __init__(self, job_id, state, source):
		self.job_id = job_id
		self.state = state
		self.source = source

	def flatten(self):
		return {'job_id': self.job_id, 'state': self.state, 'source': self.source}

class JobAuditMessage(JobStatusMessage):
	def __init__(self, job_id, state, source, title=None, summary=None, parent_id=None):
		super(JobAuditMessage, self).__init__(job_id, state, source)

		if state in constants.JOB_FINISHED_STATES and not summary:
			raise ValueError('You must supply summary in state %s' % state)
		if state == constants.JOB.NEW and not title:
			raise ValueError('You must supply a title in state %s' % state)

		self.title = title
		self.summary = summary
		self.parent_id = parent_id

	def flatten(self):
		flat = super(JobAuditMessage, self).flatten()
		flat['title'] = self.title
		flat['summary'] = self.summary
		flat['parent_id'] = self.parent_id
		return flat

class Configuration(paasmaker.util.configurationhelper.ConfigurationHelper):
	def __init__(self, io_loop=None):
		super(Configuration, self).__init__(ConfigurationSchema())
		self.port_allocator = paasmaker.util.port.FreePortFinder()
		self.plugins = paasmaker.util.PluginRegistry(self)
		self.uuid = None
		self.exchange = None
		self.job_watcher = None
		self.job_manager = paasmaker.util.jobmanager.JobManager(self)
		self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

	def load_from_file(self, search_path):
		# If we were supplied a configuration file on the command line,
		# insert that into the search path.
		new_search_path = list(search_path)
		if options.configfile != "":
			new_search_path.insert(0, options.configfile)
		super(Configuration, self).load_from_file(search_path)

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

		# Heart initialisation.
		if self.is_heart():
			# Plugins.
			self.load_plugins(self.plugins, self['heart']['plugins'])

			# Instance manager.
			self.instances = paasmaker.heart.helper.instancemanager.InstanceManager(self)

			# Mark allocated ports as allocated.
			allocated_ports = self.instances.get_used_ports()
			self.port_allocator.add_allocated_port(allocated_ports)

		# Pacemaker initialisation.
		if self.is_pacemaker():
			self.load_plugins(self.plugins, self['pacemaker']['plugins'])

		self.update_flat()

	def is_pacemaker(self):
		return self.get_flat('pacemaker.enabled')
	def is_heart(self):
		return self.get_flat('heart.enabled')
	def is_router(self):
		return self.get_flat('router.enabled')

	def get_runtimes(self):
		if not self.is_heart():
			raise ImNotAHeart("I'm not a heart, so I have no runtimes.")

		tags = {}
		runtime_plugins = self.plugins.plugins_for(paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)
		for plugin in runtime_plugins:
			runtime = self.plugins.instantiate(plugin, paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)
			versions = runtime.get_versions()

			tags[plugin] = versions

		return tags

	def setup_database(self):
		if not self.is_pacemaker():
			raise ImNotAPacemaker("I'm not a pacemaker, so I have no database.")

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
			raise ImNotA("I'm not a pacemaker, so I have no database.")
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
		return os.path.normpath(os.path.dirname(__file__) + '/../../../pm-supervisor.py')

	#
	# JOB HELPERS
	#
	def make_job_id(self, title):
		# All we need to do is allocate an ID and mark it as new.
		# The messaging subsystem will handle persisting it to the DB.
		job_id = str(uuid.uuid4())
		self.send_job_status(job_id, constants.JOB.NEW, title=title)
		return job_id
	def start_jobs(self):
		self.job_manager.evaluate()
	def get_job_logger(self, job_id):
		return paasmaker.util.joblogging.JobLoggerAdapter(logging.getLogger('job'), job_id, self, self.get_job_watcher())
	def get_job_log_path(self, job_id):
		container = os.path.join(self['log_directory'], 'job')
		checksum = hashlib.md5()
		checksum.update(job_id)
		checksum = checksum.hexdigest()
		container = os.path.join(container, checksum[0:2])
		if not os.path.exists(container):
			os.makedirs(container)
		path = os.path.join(container, checksum[2:] + '.log')
		# Create the file if it doesn't exist - prevents errors
		# trying to watch the file before anything's been written to it
		# (shouldn't be an issue for production, but causes issues in
		# unit tests with weird global log levels.)
		if not os.path.exists(path):
			fp = open(path, 'a')
			fp.close()
		return path
	def debug_cat_job_log(self, job_id):
		path = self.get_job_log_path(job_id)
		fp = open(path, 'r')
		print fp.read()
		fp.close()
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
	def setup_job_watcher(self, io_loop):
		if not self.job_watcher:
			self.job_watcher = paasmaker.util.joblogging.JobWatcher(self, io_loop)
	def get_job_watcher(self):
		return self.job_watcher
	def send_job_status(self, job_id, state, title=None, source=None, summary=None, parent_id=None):
		"""
		Propagate the status of a job to listeners who care inside our
		instance, and also likely down the Rabbit hole to other listeners.
		(Rabbit hole means RabbitMQ... so there is no confusion.)
		Sends both an audit and an update message, as appropriate.
		"""
		# If source is not supplied, send along our own UUID.
		send_source = source
		if not send_source:
			send_source = self.get_node_uuid()

		# Make the message objects.
		status = JobStatusMessage(job_id, state, send_source)
		audit = JobAuditMessage(job_id, state, send_source, title=title, summary=summary, parent_id=parent_id)

		status_topic = self.get_job_status_pub_topic(job_id)
		audit_topic = self.get_job_audit_pub_topic(job_id)

		# Send the status message.
		pub.sendMessage(status_topic, message=status)
		# And then the audit message.
		pub.sendMessage(audit_topic, message=audit)

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

	#
	# HEART HELPERS
	#
	def get_instance_path(self, instance_id):
		path = os.path.join(
			self.get_flat('heart.working_dir'),
			'instance',
			instance_id
		)

		if not os.path.exists(path):
			os.makedirs(path)

		return path

	def get_instance_package_path(self):
		path = os.path.join(
			self.get_flat('heart.working_dir'),
			'packages'
		)
		if not os.path.exists(path):
			os.makedirs(path)

		return path

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
		self.assertEqual(config.get_flat('http_port'), DEFAULT_API_PORT, 'No default present.')


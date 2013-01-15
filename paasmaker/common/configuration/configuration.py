
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
import datetime

import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationException
from paasmaker.util.configurationhelper import NoConfigurationFileException
from paasmaker.common.core import constants

from pubsub import pub
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import colander
import tornadoredis
from paasmaker.thirdparty.pika import TornadoConnection
import pika
import yaml

# For parsing command line options.
from tornado.options import define, options
import tornado.testing

# Set up logging for this module.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Set up command line options.
define("debug", type=int, default=0, help="Enable Tornado debug mode. Also prevents Paasmaker from forking into the background.")
define("configfile", type=str, default="", help="Override configuration file.")

# Default ports.
DEFAULT_API_PORT = 42500

DEFAULT_ROUTER_REDIS_MASTER = 42510
DEFAULT_ROUTER_REDIS_SLAVE = 42511
DEFAULT_ROUTER_REDIS_STATS = 42512
DEFAULT_REDIS_JOBS = 42513

DEFAULT_NGINX = 42530

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

class ScmListerSchema(colander.MappingSchema):
	for_name = colander.SchemaNode(colander.String(),
		name="for",
		title="The SCM plugin that these listers are for.")
	plugins = colander.SchemaNode(colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Plugins that list repositories.",
		default=[],
		missing=[])

class ScmListersSchema(colander.SequenceSchema):
	lister = ScmListerSchema()

class HealthPluginSchema(colander.MappingSchema):
	plugin = colander.SchemaNode(colander.String(),
		title="Plugin name",
		description="Plugin name for this particular health check.")
	order = colander.SchemaNode(colander.Integer(),
		title="Plugin order",
		description="The order of execution for this particular plugin. Plugins with the same order are run at the same time. Plugins with lower order numbers are run first. Order numbers do not need to be consecutive.")
	parameters = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Plugin Parameters",
		description="Parameters for this particular plugin",
		missing={},
		default={})

class HealthPluginsSchema(colander.SequenceSchema):
	health = HealthPluginSchema()

	@staticmethod
	def default():
		return {'plugins': []}

class HealthGroupSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Symbolic name",
		description="The symbolic name for this health check group.")
	title = colander.SchemaNode(colander.String(),
		title="Friendly name",
		description="The friendly name for this health check group.")
	period = colander.SchemaNode(colander.Integer(),
		title="Group recheck period",
		description="How often to run this health check group, in seconds.")
	plugins = HealthPluginsSchema(
		default=HealthPluginsSchema.default(),
		missing=HealthPluginsSchema.default()
	)

class HealthGroupsSchema(colander.SequenceSchema):
	group = HealthGroupSchema()

class HealthGroupsOnlySchema(colander.MappingSchema):
	groups = HealthGroupsSchema()

class HealthCombinedSchema(colander.MappingSchema):
	groups = HealthGroupsSchema(
		missing=[],
		default=[]
	)
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Run health checks",
		description="If true, run health checks on this node. If you have multiple pacemakers, you will only want to run this on one node. However, you could configure two pacemakers to perform different health checks.",
		missing=True,
		default=True)
	default = colander.SchemaNode(colander.Boolean(),
		title="Include default health checks",
		description="Include default health checks. These are added to any groups. If you do enable this, you should not define a 'default' group.",
		missing=True,
		default=True)

	@staticmethod
	def default():
		return {'enabled': False, 'groups': []}

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

	scmlisters = ScmListersSchema(
		title="SCM listers",
		description="A set of SCM listers and their matching SCMs.",
		missing=[],
		default=[])

	cluster_hostname = colander.SchemaNode(colander.String(),
		title="Cluster Hostname",
		description="The hostname postfix used to automatically generate hostnames when required. Eg, each application version gets a URL - N.<applicatio>.cluster_hostname.")
	pacemaker_prefix = colander.SchemaNode(colander.String(),
		title="Pacemaker Prefix",
		description="The prefix added to the cluster hostname to make a url for the pacemakers.",
		missing="pacemaker",
		default="pacemaker")

	# TODO: Consider the security implications of this more.
	allow_supertoken = colander.SchemaNode(colander.Boolean(),
		title="Allow Super Token authentication",
		description="If true, enable super token authentication.",
		default=False,
		missing=False)
	super_token = colander.SchemaNode(colander.String(),
		title="Super authentication token",
		description="An authentication token that can be used to do anything, specifically designed to bootstrap the system. Also used for encrypting cookies.")

	run_crons = colander.SchemaNode(colander.Boolean(),
		title="Run cron tasks",
		description="If true, run the cron tasks on this node. If you have multiple pacemakers, you won't want to do this on two of them.",
		missing=True,
		default=True)

	allow_uploads = colander.SchemaNode(colander.Boolean(),
		title="Enable file uploads",
		description="Allow file uploads to this node.",
		missing=True,
		default=True)

	health = HealthCombinedSchema(
		missing=HealthCombinedSchema.default(),
		default=HealthCombinedSchema.default()
	)

	@staticmethod
	def default():
		return {'enabled': False, 'scmlisters': [], 'health': HealthCombinedSchema.default()}

class HeartSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Heart enabled",
		description="Heart is enabled for this node",
		missing=False,
		default=False)

	working_dir = colander.SchemaNode(colander.String(),
		title="Working directory",
		description="Directory where heart working files are stored")

	@staticmethod
	def default():
		return {'enabled': False}

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
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown with node",
		description="If true, this managed redis instance is shut down when the node is shut down.",
		default=False,
		missing=False)

	@staticmethod
	def default_router_table():
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_MASTER, 'managed': False, 'shutdown': False}
	@staticmethod
	def default_router_stats():
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_STATS, 'managed': False, 'shutdown': False}
	@staticmethod
	def default_jobs():
		return {'host': 'localhost', 'port': DEFAULT_REDIS_JOBS, 'managed': False, 'shutdown': False}

class RedisConnectionSlaveSchema(RedisConnectionSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Enable automatic slaving",
		description="Enable automatic slaving of this router table to the supplied values.",
		missing=False,
		default=False)

	@staticmethod
	def default():
		return {'enabled': False}

class NginxSchema(colander.MappingSchema):
	managed = colander.SchemaNode(colander.Boolean(),
		title="Enable managed nginx",
		description="If enabled, a managed version of NGINX is started as appropriate, pointing to the correct resources for this node. Note that you must specify a port, and it must be >1024, as this node won't be run as root.",
		default=False,
		missing=False)
	port = colander.SchemaNode(colander.Integer(),
		title="Managed NGINX port",
		description="The port to run the managed NGINX on.",
		default=DEFAULT_NGINX,
		missing=DEFAULT_NGINX)
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown with node",
		description="If true, this managed nginx instance is shut down when the node is shut down.",
		default=False,
		missing=False)

	@staticmethod
	def default():
		return {'managed': False, 'port': DEFAULT_NGINX, 'shutdown': False}

class RouterSchema(colander.MappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Router enabled",
		description="Router is enabled for this node",
		missing=False,
		default=False)

	process_stats = colander.SchemaNode(colander.Boolean(),
		title="Process Stats",
		description="If true, process the special JSON formatted nginx log file for statistics.",
		default=True,
		missing=True)

	stats_log = colander.SchemaNode(colander.String(),
		title="Stats log location",
		description="NGINX Paasmaker stats log file location")

	stats_interval = colander.SchemaNode(colander.Integer(),
		title="Stats read interval",
		description="The interval between reading log files, in milliseconds.",
		default=500,
		missing=500)

	nginx = NginxSchema(missing=NginxSchema.default(), default=NginxSchema.default())

	@staticmethod
	def default():
		return {
			'enabled': False,
			'nginx': NginxSchema.default()
		}

class RedisSchema(colander.MappingSchema):
	table = RedisConnectionSchema(default=RedisConnectionSchema.default_router_table(), missing=RedisConnectionSchema.default_router_table())
	stats = RedisConnectionSchema(default=RedisConnectionSchema.default_router_stats(), missing=RedisConnectionSchema.default_router_stats())
	slaveof = RedisConnectionSlaveSchema(default=RedisConnectionSlaveSchema.default(), missing=RedisConnectionSlaveSchema.default())
	jobs = RedisConnectionSchema(default=RedisConnectionSchema.default_jobs(), missing=RedisConnectionSchema.default_jobs())

	@staticmethod
	def default():
		return {
			'table': RedisConnectionSchema.default_router_table(),
			'stats': RedisConnectionSchema.default_router_stats(),
			'slaveof': RedisConnectionSlaveSchema.default(),
			'jobs': RedisConnectionSchema.default_jobs()
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

	default_plugins = colander.SchemaNode(colander.Boolean(),
		title="Set up default plugins",
		description="If true, sets up a set of internal plugins for job handling and other tasks. If you turn this off, you will have full control over all plugins - and will need to include job plugins.",
		missing=True,
		default=True)

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

	node_token = colander.SchemaNode(colander.String(),
		title="Node Authentication Token",
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

	pid_path = colander.SchemaNode(colander.String(),
		title="PID path",
		description="The path at which to write the PID file.",
		default="paasmaker.pid",
		missing="paasmaker.pid")

	master = MasterSchema(default=MasterSchema.default(), missing=MasterSchema.default())

	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes. Applications are passed these tags as well, so you will want to be careful what you put in here.",
		missing={},
		default={})

	single_node = colander.SchemaNode(colander.Boolean(),
		title="Single node mode",
		description="In single node mode, a few dependant services are not required and thus not started.",
		default=False,
		missing=False)

	node_report_interval = colander.SchemaNode(colander.Integer(),
		title="Node report interval",
		description="How long in milliseconds between reports back to the master node. Default 60seconds.",
		default=60000,
		missing=60000)

	pacemaker = PacemakerSchema(default=PacemakerSchema.default(), missing=PacemakerSchema.default())
	heart = HeartSchema(defalt=HeartSchema.default(), missing=HeartSchema.default())
	router = RouterSchema(default=RouterSchema.default(), missing=RouterSchema.default())

	redis = RedisSchema(default=RedisSchema.default(), missing=RedisSchema.default())

	plugins = PluginsSchema(
		title="Plugins",
		description="A list of plugins registered on this node. It's up to you to make sure they're applicable for this node type.",
		missing=[],
		default=[])

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

class PluginsOnlySchema(colander.MappingSchema):
	plugins = PluginsSchema(
		title="Plugins",
		description="The list of plugins.",
		missing=[],
		default=[])

class ImNotA(Exception):
	"""
	Base exception thrown when a configuration method
	is called that is not supported by the node type.
	"""
	pass

class ImNotAHeart(ImNotA):
	"""
	Thrown when a heart-only method is called from a non-heart node.
	"""
	pass

class ImNotAPacemaker(ImNotA):
	"""
	Thrown when a pacemaker-only method is called from a non-pacemaker
	node.
	"""
	pass

class ImNotARouter(ImNotA):
	"""
	Thrown when a router-only method is called from a non-router node.
	"""
	pass

class JobStatusMessage(object):
	"""
	A job status message object that is passed to any subscribers to
	the internal job status notification.

	:arg str job_id: The job ID.
	:arg str state: One of the state constants for a job.
	:arg str source: The UUID of the node that originated this
		message.
	:arg str|None parent_id: The parent ID of this job. Typically
		only set when the job is NEW.
	:arg str|None summary: The summary of the job. Only set when
		the job enters a finished state.
	"""
	def __init__(self, job_id, state, source, parent_id=None, summary=None):
		self.job_id = job_id
		self.state = state
		self.source = source
		self.parent_id = parent_id
		self.summary = summary

	def flatten(self):
		"""
		Flatten the internal variables into a dict.
		"""
		return {
			'job_id': self.job_id,
			'state': self.state,
			'source': self.source,
			'parent_id': self.parent_id,
			'summary': self.summary
		}

class Configuration(paasmaker.util.configurationhelper.ConfigurationHelper):
	"""
	The main configuration object for the Paasmaker system.

	This object contains the configuration and context for the entire
	application. Most components in the system accept an instance of
	this object, and use that to look up shared resources such as database
	sessions, Redis instances, or other information.

	This class also handles loading the configuration file as well,
	and validating it's contents. Additionally, it also handles plugins.

	Instance variables that are available for public use:

	* **plugins**: The plugin registry instance for the system. You
	  can call this to instantiate plugins. For example::

	  	self.configuration.plugins.instantiate( ... )

	* **io_loop**: The tornado IO loop. Use the IO loop from this
	  object directly wherever you need one. This is because the
	  ``ConfigurationStub()`` class will have this set correctly,
	  meaning your production code and unit test code are identical.
	* **job_manager**: You can acces the job manager directly from
	  here when needed.

	Other instance variables, whilst not prefixed with an underscore,
	should be considered protected. Only use the instance variables
	documented above in your code.

	To access the configuration options, you have two options:

	* Use the configuration object as a dict, checking for keys
	  as nessecary before trying to access keys that may or may not
	  be present. For example::

	  	pacemaker = configuration['pacemaker']['enabled']

	* Use the ``get_flat()`` method with a path. For example::

		pacemaker = configuration.get_flat('pacemaker.enabled')

	"""
	def __init__(self, io_loop=None):
		super(Configuration, self).__init__(ConfigurationSchema())
		self.port_allocator = paasmaker.util.port.FreePortFinder()
		self.plugins = paasmaker.util.PluginRegistry(self)
		self.uuid = None
		self.job_watcher = None
		self.job_manager = paasmaker.common.job.manager.manager.JobManager(self)
		self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
		self.start_time = datetime.datetime.utcnow()

	def uptime(self):
		"""
		Calculate the uptime of this configuration object, and return
		a value in seconds.
		"""
		return (datetime.datetime.utcnow() - self.start_time).total_seconds()

	def load_from_file(self, search_path):
		"""
		Load the configuration from file. If a specific configuration
		file was specified on the command line, attempt to load
		from that file.
		"""
		# If we were supplied a configuration file on the command line,
		# insert that into the search path.
		new_search_path = list(search_path)
		if options.configfile != "":
			new_search_path.insert(0, options.configfile)
		super(Configuration, self).load_from_file(new_search_path)

	def post_load(self):
		"""
		Perform post configuration loading tasks.

		This creates directories as needed, determines things like
		the hostname and route (if required), registers plugins,
		including default plugins.
		"""
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
			# Instance manager.
			self.instances = paasmaker.heart.helper.instancemanager.InstanceManager(self)

			# Mark allocated ports as allocated.
			allocated_ports = self.instances.get_used_ports()
			self.port_allocator.add_allocated_port(allocated_ports)

		if self.get_flat('default_plugins'):
			# TODO: Split into Heart/Pacemaker/Router only jobs.
			default_path = os.path.normpath(os.path.dirname(__file__) + '/../../data/defaults')
			default_file = os.path.join(default_path, 'plugins.yml')
			default_plugins_raw = open(default_file, 'r').read()
			default_plugins_parsed = yaml.safe_load(default_plugins_raw)
			default_plugins_ready = PluginsOnlySchema().deserialize(default_plugins_parsed)

			self.load_plugins(self.plugins, default_plugins_ready['plugins'])

		if self.is_pacemaker() and self.get_flat('pacemaker.health.enabled'):
			# Load the default health groups. We merge these with the others - although
			# if you duplicate the default group in yours, the results will be undefined.
			default_file = os.path.join(default_path, 'health.yml')
			default_health_raw = open(default_file, 'r').read()
			default_health_parsed = yaml.safe_load(default_health_raw)

			default_health_ready = HealthGroupsOnlySchema().deserialize(default_health_parsed)

			self['pacemaker']['health']['groups'].extend(default_health_ready['groups'])

		# Plugins. Note that we load these after the defaults,
		# so you can re-register the defaults with different options.
		self.load_plugins(self.plugins, self['plugins'])

		# TODO: validate the contents of scmlisters, that they all
		# are relevant plugins.
		# TODO: validate the health manager plugins exist.

		self.update_flat()

	def is_pacemaker(self):
		"""
		Determine if this node is a pacemaker.
		"""
		return self.get_flat('pacemaker.enabled')
	def is_heart(self):
		"""
		Determine if this node is a heart.
		"""
		return self.get_flat('heart.enabled')
	def is_router(self):
		"""
		Determine if this node is a router.
		"""
		return self.get_flat('router.enabled')

	def get_runtimes(self):
		"""
		Get a list of runtimes and their associated versions.

		Once the list is generated, it is cached for the lifetime
		of the server. Subsequent calls return the same list generated
		the first time.
		"""
		if not self.is_heart():
			raise ImNotAHeart("I'm not a heart, so I have no runtimes.")

		# Use a cached version if present.
		# The idea is that we don't do this expensive version determination each
		# time we re-register with the master.
		if hasattr(self, '_runtime_cache'):
			logger.info("Using existing runtime cache.")
			return self._runtime_cache
		else:
			logger.info("Generating runtime list...")

		tags = {}
		runtime_plugins = self.plugins.plugins_for(paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)
		for plugin in runtime_plugins:
			runtime = self.plugins.instantiate(plugin, paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)
			versions = runtime.get_versions()

			tags[plugin] = versions

		self._runtime_cache = tags
		return self._runtime_cache

	def setup_database(self):
		"""
		Set up the database; creating tables on the first startup,
		or otherwise doing nothing on subsequent operations.
		"""
		if not self.is_pacemaker():
			raise ImNotAPacemaker("I'm not a pacemaker, so I have no database.")

		# Connect.
		self.engine = create_engine(self.get_flat('pacemaker.dsn'))
		self.session = sessionmaker(bind=self.engine)

		# Create the tables.
		paasmaker.model.Base.metadata.bind = self.engine
		paasmaker.model.Base.metadata.create_all()

	def get_free_port(self):
		"""
		Get a free TCP port in the misc ports range.
		"""
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

	def _connect_redis(self, credentials, callback, error_callback):
		"""
		Internal function to connect to the given redis server, calling
		the callback when it's ready with the client object.

		You should not call this externally.

		:arg dict credentials: A dict containing three keys, ``host``,
			``port``, and ``password``.
		:arg callable callback: The callback to call when completed. The
			callback is passed the client object, an instance of
			``tornadoredis.Client``.
		:arg callable error_callback: A callback called if an error occurs.
		"""
		client = tornadoredis.Client(
			host=credentials['host'],
			port=credentials['port'],
			password=credentials['password'],
			io_loop=self.io_loop
		)
		client.connect()

		# TODO: Handle where it failed.
		callback(client)

	def _get_redis(self, name, credentials, callback, error_callback):
		"""
		Internal helper to get a redis connection.
		* Not a managed redis? Proceed to fetching a connection.
		* A managed redis? And not started? Start it, and then
		  return a client to it.
		* A managed redis? And still starting up? Queue up the incoming
		  requests.
		* A managed redis that's started? Proceed to fetching a connection.
		"""
		if not credentials['managed']:
			# It's not managed. Just attempt to connect to it.
			self._connect_redis(credentials, callback, error_callback)
		else:
			# It's managed. Check it's state.
			meta_key = "%s_%d" % (credentials['host'], credentials['port'])
			if not hasattr(self, 'redis_meta'):
				self.redis_meta = {}
			if not self.redis_meta.has_key(meta_key):
				self.redis_meta[meta_key] = {
					'state': 'CREATE',
					'queue': [],
					'shutdown': credentials['shutdown']
				}

			meta = self.redis_meta[meta_key]

			# Callback to handle when it's up and running.
			def on_redis_started(message):
				# Mark it as started.
				# TODO: Detect and handle where it didn't start.
				meta['state'] = 'STARTED'

				# Play back all our callbacks.
				for queued in meta['queue']:
					self._connect_redis(queued[0], queued[1], queued[2])

			def on_redis_startup_failure(message, exception=None):
				# TODO: Handle this.
				pass

			# Change the action based on our state.
			if meta['state'] == 'CREATE':
				# This is the first attempt to access it.
				# Start up the service.
				meta['state'] = 'STARTING'
				meta['queue'].append((credentials, callback, error_callback))

				directory = self.get_scratch_path_exists(
					'redis', name
				)
				meta['manager'] = paasmaker.util.managedredis.ManagedRedis(self)
				try:
					meta['manager'].load_parameters(directory)
				except paasmaker.util.ManagedDaemonError, ex:
					# Doesn't yet exist. Create it.
					meta['manager'].configure(directory, credentials['port'], credentials['host'], credentials['password'])

				meta['manager'].start_if_not_running(on_redis_started, on_redis_startup_failure)

			elif meta['state'] == 'STARTING':
				# Queue up our callbacks.
				meta['queue'].append((credentials, callback, error_callback))
			else:
				# Must be started. Just connect.
				self._connect_redis(credentials, callback, error_callback)

	def get_router_table_redis(self, callback, error_callback):
		"""
		Get a redis client pointing to the router table Redis instance.

		On router nodes, this will return a connection to the slave
		redis. On pacemaker nodes, this will instead be the master.
		This is dependant on the server configuration.
		"""
		self._get_redis('table', self['redis']['table'], callback, error_callback)

	def get_stats_redis(self, callback, error_callback):
		"""
		Get a redis client pointing to the stats Redis instance.

		For multi node setups, this will generally point to the same
		instance of Redis, on a single host.
		"""
		self._get_redis('stats', self['redis']['stats'], callback, error_callback)

	def get_jobs_redis(self, callback, error_callback):
		"""
		Get a redis client pointing to the jobs Redis instance.

		For multi node setups, this will generally point to the same
		instance of Redis, on a single host.
		"""
		self._get_redis('jobs', self['redis']['jobs'], callback, error_callback)

	def shutdown_managed_redis(self):
		"""
		Shutdown any managed redis instances for which we've been
		configured to shutdown on exit.

		This has no action if no Redis instances have been configured
		to shutdown on exit.
		"""
		if hasattr(self, 'redis_meta'):
			for key, meta in self.redis_meta.iteritems():
				if meta['state'] == 'STARTED' and meta['shutdown']:
					logger.info("Shutting down managed redis, because requested to do so.")
					meta['manager'].stop()
					# Wait until it stops.
					while meta['manager'].is_running():
						pass

	def setup_managed_nginx(self, callback, error_callback):
		"""
		Setup, and start if nessecary a managed NGINX instance
		for this node, calling the callback when this task is complete.

		Has no action if this node is not managing an NGINX instance.
		"""
		if self.get_flat('router.nginx.managed'):
			# Fire up the managed version, if it's not already running.
			self.nginx_server = paasmaker.util.managednginx.ManagedNginx(self)
			directory = self.get_scratch_path('nginx')
			try:
				self.nginx_server.load_parameters(directory)
			except paasmaker.util.ManagedDaemonError, ex:
				# Doesn't yet exist. Create it.
				self.nginx_server.configure(
					directory,
					self.get_flat('router.nginx.port')
				)

			def on_nginx_started(message):
				# Set the stats log path manually.
				self['router']['stats_log'] = os.path.join(directory, 'access.log.paasmaker')
				self.update_flat()

				# And let the caller know we're ready.
				callback(message)

			def on_nginx_failed(message, exception=None):
				error_callback(message, exception)

			self.nginx_server.start_if_not_running(on_nginx_started, on_nginx_failed)
		else:
			# It's not managed. Do nothing.
			callback("NGINX not managed - no action taken.")

	def shutdown_managed_nginx(self):
		"""
		If configured, shutdown an associated managed NGINX instance
		on exit.
		"""
		if self.get_flat('router.nginx.managed') and self.get_flat('router.nginx.shutdown'):
			# Shut down the managed nginx, if it's running.
			if self.nginx_server.is_running():
				self.nginx_server.stop()

	def get_tornado_configuration(self):
		"""
		Return a dict of settings that are passed to Tornado's HTTP
		listener, to configure various framework options. The
		returned settings are based on the configuration of the system.
		"""
		settings = {}
		# If we're a pacemaker, the cookie secret is the cluster name
		# and the super token combined.
		# Otherwise, it's the node token, although non-pacemaker nodes
		# should not be assigning cookies.
		if self.is_pacemaker():
			settings['cookie_secret'] = "%s-%s" % (self.get_flat('pacemaker.cluster_hostname'), self.get_flat('pacemaker.super_token'))
		else:
			settings['cookie_secret'] = self['node_token']
		settings['template_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../templates')
		settings['static_path'] = os.path.normpath(os.path.dirname(__file__) + '/../../static')
		settings['debug'] = (options.debug == 1)
		settings['xheaders'] = True
		if not settings['debug']:
			# Turn on GZIP encoding, when not in debug mode.
			settings['gzip'] = True
		return settings

	def get_scratch_path(self, *args):
		"""
		Get a absolute path to a filename in the scratch directory.

		The filename is joined onto the scratch directory and then
		returned. The path may not exist; use ``get_scratch_path_exists()``
		to handle this case.
		"""
		return os.path.join(self.get_flat('scratch_directory'), *args)

	def get_scratch_path_exists(self, *args):
		"""
		This is the same as ``get_scratch_path()`` except it makes
		sure the directories including and leading up to it exist
		before returning the path.
		"""
		path = os.path.join(self.get_flat('scratch_directory'), *args)
		if not os.path.exists(path):
			os.makedirs(path)
		return path

	def get_supervisor_path(self):
		"""
		Get the path to the pm-supervisor.py command, determined relative
		to this installation or copy of Paasmaker.
		"""
		return os.path.normpath(os.path.dirname(__file__) + '/../../../pm-supervisor.py')

	#
	# JOB HELPERS
	#
	def startup_job_manager(self, callback=None, error_callback=None):
		"""
		Set up the job manager.

		This should be called before working with the job manager.
		This asks the job manager to set up any database connections
		it may need to work.
		"""
		self.job_manager.prepare(callback, error_callback)

	def startup_health_manager(self, start_checking=True):
		"""
		Set up the health manager.

		This should be called on startup to set up the health manager.

		:arg bool start_checking: If True, start checking according
			to the configured schedule. This parameter is intended for
			unit tests, to disable the default behaviour.
		"""
		if not self.is_pacemaker():
			raise ImNotAPacemaker("Only pacemakers can run health checks.")

		self.health_manager = paasmaker.pacemaker.helper.healthmanager.HealthManager(self)

		if start_checking:
			self.health_manager.start()

	def start_jobs(self):
		"""
		Evaluate any pending jobs, and begin executing any that
		can be run now.
		"""
		self.job_manager.evaluate()
	def get_job_logger(self, job_id):
		"""
		Get a JobLoggingAdapter for the given job ID.
		:arg str job_id: The job ID to fetch the logger for.
		"""
		return paasmaker.util.joblogging.JobLoggerAdapter(
			logging.getLogger('job'),
			job_id,
			self,
			self.get_job_watcher()
		)
	def get_job_log_path(self, job_id, create_if_missing=True):
		"""
		Get the absolute path to a job log file.

		Useful if the job log file is to be used outside of
		the normal logging system, or for checking if it
		exists or otherwise working with it.

		:arg str job_id: The job ID to fetch the path for.
		:arg bool create_if_missing: If true, ensure that
			the file exists before returning. This works
			around some issues in unit tests, but should be
			set to false if determining the existence of log
			files.
		"""
		# TODO: Make this safer, but maintain the job id's relating to their on disk
		# filenames.
		if job_id.find('.') != -1 or job_id.find('/') != -1:
			raise ValueError("Invalid and unsafe job ID.")

		container = os.path.join(
			self['log_directory'],
			'job',
			job_id[0:2]
		)
		if not os.path.exists(container) and create_if_missing:
			os.makedirs(container)
		path = os.path.join(container, job_id[2:] + '.log')
		# Create the file if it doesn't exist - prevents errors
		# trying to watch the file before anything's been written to it
		# (shouldn't be an issue for production, but causes issues in
		# unit tests with weird global log levels.)
		if not os.path.exists(path) and create_if_missing:
			fp = open(path, 'a')
			fp.close()
		return path
	def debug_cat_job_log(self, job_id):
		"""
		For debugging, directly print the entire contents of a job
		log file to screen by using print.

		:arg str job_id: The job ID to dump.
		"""
		path = self.get_job_log_path(job_id)
		fp = open(path, 'r')
		print fp.read()
		fp.close()
	def get_job_message_pub_topic(self, job_id):
		"""
		Fetch the pub-sub topic for a new-messages-available
		topic, for a specific job ID.

		:arg str job_id: The job ID to fetch the topic for.
		"""
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'message', 'j' + job_id)
	def get_job_status_pub_topic(self, job_id):
		"""
		Fetch the pub-sub topic for a job-status
		topic, for a specific job ID.

		:arg str job_id: The job ID to fetch the topic for.
		"""
		# Why add the 'j' to the job name? It seems a topic name
		# can't start with a number.
		return ('job', 'status', 'j' + job_id)
	def job_exists_locally(self, job_id):
		"""
		Check to see if a log file exists for the given
		job on this node.

		:arg str job_id: The job ID to check for.
		"""
		path = self.get_job_log_path(job_id, create_if_missing=False)
		return os.path.exists(path)
	def setup_job_watcher(self):
		"""
		Set up the job log watcher helper class.
		"""
		if not self.job_watcher:
			self.job_watcher = paasmaker.util.joblogging.JobWatcher(self)
	def get_job_watcher(self):
		"""
		Get the job watcher instance.
		"""
		return self.job_watcher
	def send_job_status(self, job_id, state, source=None, parent_id=None, summary=None):
		"""
		Propagate the status of a job to listeners inside our
		instance, and also likely to other nodes as well. The Job manager
		is responsible for getting the status to other nodes.

		:arg str job_id: The job ID that this status update is for.
		:arg str state: The state of the job.
		:arg str|None source: The source of the job. This is for internal
			use, to track the node who sent the status update in the
			first place. Unless you know what you're doing, leave this as None.
		:arg str|None parent_id: The parent ID of a new job. The job manager
			should handle notifications of new jobs, so leave this as None.
		:arg str|None summary: The summary of a job, sent when the job changes
			into a finished state. The job manager handles suppling this when
			needed.
		"""
		# If source is not supplied, send along our own UUID.
		send_source = source
		if not send_source:
			send_source = self.get_node_uuid()

		# Make the message objects.
		status = JobStatusMessage(job_id, state, send_source, parent_id=parent_id, summary=summary)

		status_topic = self.get_job_status_pub_topic(job_id)

		# Send the status message.
		pub.sendMessage(status_topic, message=status)

	#
	# IDENTITY HELPERS
	#
	def set_node_uuid(self, uuid):
		"""
		Set our nodes UUID, saving it to an appropriate location.

		:arg str uuid: The node's UUID.
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
			return None

		return self.uuid

	#
	# HEART HELPERS
	#
	def get_instance_path(self, instance_id):
		"""
		Heart nodes - get the path to the working directory
		for a given instance ID. Creates the directory if
		it does not already exist.

		:arg str instance_id: The instance ID.
		"""
		path = os.path.join(
			self.get_flat('heart.working_dir'),
			'instance',
			instance_id
		)

		if not os.path.exists(path):
			os.makedirs(path)

		return path

	def get_instance_package_path(self):
		"""
		Get the path where packed applications are stored.
		Creates the path if required.
		"""
		path = os.path.join(
			self.get_flat('heart.working_dir'),
			'packages'
		)
		if not os.path.exists(path):
			os.makedirs(path)

		return path

	def instance_status_trigger(self):
		"""
		Heart nodes - trigger an instance status report to the master
		right now. Used when you know that the instance statuses have changed.
		"""
		if hasattr(self, 'node_register_periodic'):
			# Trigger a call to update the master with instance statuses.
			# This will do one at a time, but stack them to it's always up
			# to date.
			self.node_register_periodic.trigger()

class TestConfiguration(unittest.TestCase):
	minimum_config = """
node_token: 5893b415-f166-41a8-b606-7bdb68b88f0b
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


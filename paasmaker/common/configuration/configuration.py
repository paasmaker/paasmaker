#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
import time
import copy
import traceback
from distutils.spawn import find_executable

import paasmaker
from paasmaker.util.configurationhelper import InvalidConfigurationParameterException
from paasmaker.util.configurationhelper import InvalidConfigurationFormatException
from paasmaker.util.configurationhelper import NoConfigurationFileException
from paasmaker.util.configurationhelper import StrictAboutExtraKeysColanderMappingSchema
from paasmaker.common.core import constants

from pubsub import pub
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
import sqlalchemy
import colander
from paasmaker.thirdparty.pika import TornadoConnection
from paasmaker.thirdparty.tornadoredis import Client as TornadoRedisClient
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

DEFAULT_NGINX_DIRECT = 42530
DEFAULT_NGINX_PORT80 = 42531
DEFAULT_NGINX_PORT443 = 42532

DEFAULT_APPLICATION_MIN = 42600
DEFAULT_APPLICATION_MAX = 42699

# The Configuration Schema.
class PluginSchema(StrictAboutExtraKeysColanderMappingSchema):
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

class PeriodicSchema(StrictAboutExtraKeysColanderMappingSchema):
	plugin = colander.SchemaNode(colander.String(),
		title="Periodic Plugin",
		description="The periodic plugin to run.")
	interval = colander.SchemaNode(colander.Integer(),
		title="Periodic Interval",
		description="How often to run this periodic plugin.")

class PeriodicsSchema(colander.SequenceSchema):
	periodic = PeriodicSchema()

class PeriodicsOnlySchema(StrictAboutExtraKeysColanderMappingSchema):
	periodics = PeriodicsSchema()

class ScmListerSchema(StrictAboutExtraKeysColanderMappingSchema):
	for_name = colander.SchemaNode(colander.String(),
		name="for",
		title="SCM name",
		description="The SCM that this list of listers is for.")
	plugins = colander.SchemaNode(colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Plugins List",
		description="A list of plugin names that can list repositories for this SCM.",
		default=[],
		missing=[])

class ScmListersSchema(colander.SequenceSchema):
	lister = ScmListerSchema()

class HealthPluginSchema(StrictAboutExtraKeysColanderMappingSchema):
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

class HealthGroupSchema(StrictAboutExtraKeysColanderMappingSchema):
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
		title="Plugins",
		description="A set of plugins and their run order.",
		default=HealthPluginsSchema.default(),
		missing=HealthPluginsSchema.default()
	)

class HealthGroupsSchema(colander.SequenceSchema):
	group = HealthGroupSchema()

class HealthGroupsOnlySchema(StrictAboutExtraKeysColanderMappingSchema):
	groups = HealthGroupsSchema()

class HealthCombinedSchema(StrictAboutExtraKeysColanderMappingSchema):
	groups = HealthGroupsSchema(
		missing=[],
		default=[]
	)
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Run health checks",
		description="If true, run health checks on this node. If you have multiple pacemakers, you will only want to run this on one node. However, you could configure two pacemakers to perform different health checks.",
		missing=True,
		default=True)
	use_default_checks = colander.SchemaNode(colander.Boolean(),
		title="Include default health checks",
		description="Include default health checks. These are added to any groups. If you do enable this, you should not define a 'default' group. The default checks are in paasmaker/data/defaults/health.yml.",
		missing=True,
		default=True)

	@staticmethod
	def default():
		return {'enabled': True, 'groups': [], 'use_default_checks': True}

class PacemakerSchema(StrictAboutExtraKeysColanderMappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Pacemaker enabled",
		description="Pacemaker is enabled for this node",
		missing=False,
		default=False)

	require_ssl = colander.SchemaNode(
		colander.Boolean(),
		title="Require SSL",
		description="If true, require SSL for access to the console and API.",
		missing=False,
		default=False
	)

	dsn = colander.SchemaNode(colander.String(),
		title="Database DSN",
		description="Database connection details for this pacemaker, in SQLAlchemy format")

	database_options = colander.SchemaNode(
		colander.Mapping(unknown='preserve'),
		title="Additional Database options",
		description="Additional Database options, passed as keyword arguments to engine_create. See http://docs.sqlalchemy.org/en/rel_0_7/core/engines.html#engine-creation-api for the available options. This can be used to tweak database connection details.",
		missing={},
		default={})

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
		description="The hostname postfix used to automatically generate hostnames when required. Eg, each application version gets a URL - N.<type>.<application>.cluster_hostname.")
	pacemaker_prefix = colander.SchemaNode(colander.String(),
		title="Pacemaker Prefix",
		description="The prefix added to the cluster hostname to make a hostname for the pacemakers.",
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
		description="If true, run the cron tasks on this node. If you have multiple pacemakers, you won't want to do this on more than one of them.",
		missing=True,
		default=True)

	allow_uploads = colander.SchemaNode(colander.Boolean(),
		title="Enable file uploads",
		description="Allow file uploads to this node.",
		missing=True,
		default=True)

	health = HealthCombinedSchema(
		title="Health Check configuration",
		description="Options for the health checking system.",
		missing=HealthCombinedSchema.default(),
		default=HealthCombinedSchema.default()
	)

	frontend_domain_postfix = colander.SchemaNode(colander.String(),
		title="Frontend domain name postfix",
		description="In the web interface, append this string to any hostnames that the system generates for users. This is designed to add your router's port to the cluster domain name at display time.",
		default="",
		missing="")

	node_connectivity_check_timeout = colander.SchemaNode(
		colander.Float(),
		title="Node Connectivity Check timeout",
		description="The timeout when hitting the /info endpoint on a remote node before accepting it's registration.",
		default=1.0,
		missing=1.0
	)

	@staticmethod
	def default():
		return {'enabled': False, 'scmlisters': [], 'health': HealthCombinedSchema.default()}

class HeartSchema(StrictAboutExtraKeysColanderMappingSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Heart enabled",
		description="Heart is enabled for this node",
		missing=False,
		default=False)

	working_dir = colander.SchemaNode(colander.String(),
		title="Working directory",
		description="Directory where active application instance files are stored. By default, Paasmaker will choose a path inside the scratch directory. You can customize this if your heart node has a special storage location optimised for application instances.",
		# None here means to automatically figure out the path.
		missing=None,
		default=None)

	shutdown_on_exit = colander.SchemaNode(colander.Boolean(),
		title="Shutdown applications on exit",
		description="Shutdown all applications on exit, rather than leaving them running. This is designed for testing and development, and not for production.",
		default=False,
		missing=False)

	@staticmethod
	def default():
		return {'enabled': False}

class RedisConnectionSchema(StrictAboutExtraKeysColanderMappingSchema):
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
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_MASTER, 'password': None, 'managed': True, 'shutdown': False}
	@staticmethod
	def default_router_stats():
		return {'host': 'localhost', 'port': DEFAULT_ROUTER_REDIS_STATS, 'password': None, 'managed': True, 'shutdown': False}
	@staticmethod
	def default_jobs():
		return {'host': 'localhost', 'port': DEFAULT_REDIS_JOBS, 'password': None, 'managed': True, 'shutdown': False}

class RedisConnectionSlaveSchema(RedisConnectionSchema):
	enabled = colander.SchemaNode(colander.Boolean(),
		title="Enable automatic slaving",
		description="Enable automatic slaving of this router table to the supplied values.",
		missing=False,
		default=False)

	@staticmethod
	def default():
		return {'enabled': False}

class NginxSchema(StrictAboutExtraKeysColanderMappingSchema):
	managed = colander.SchemaNode(colander.Boolean(),
		title="Enable managed nginx",
		description="If enabled, a managed version of NGINX is started as appropriate, pointing to the correct resources for this node. Note that you must specify a port, and it must be >1024, as this node won't be run as root.",
		default=False,
		missing=False)
	port_direct = colander.SchemaNode(colander.Integer(),
		title="Managed NGINX port - direct connection",
		description="The port to run the managed NGINX on. This port sends X-Forwarded-Port: <port_direct> to applications.",
		default=DEFAULT_NGINX_DIRECT,
		missing=DEFAULT_NGINX_DIRECT)
	port_80 = colander.SchemaNode(colander.Integer(),
		title="Managed NGINX port - port 80",
		description="The port to run the managed NGINX on. This port sends X-Forwarded-Port: 80 to applications.",
		default=DEFAULT_NGINX_PORT80,
		missing=DEFAULT_NGINX_PORT80)
	port_443 = colander.SchemaNode(colander.Integer(),
		title="Managed NGINX port - port 443",
		description="The port to run the managed NGINX on. This port sends X-Forwarded-Port: 443 and X-Forwarded-Proto: https to applications.",
		default=DEFAULT_NGINX_PORT443,
		missing=DEFAULT_NGINX_PORT443)
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown with node",
		description="If true, this managed nginx instance is shut down when the node is shut down.",
		default=False,
		missing=False)

	@staticmethod
	def default():
		return {'managed': True, 'port_direct': DEFAULT_NGINX_DIRECT, 'port_80': DEFAULT_NGINX_PORT80, 'port_443': DEFAULT_NGINX_PORT443, 'shutdown': False}

class RouterSchema(StrictAboutExtraKeysColanderMappingSchema):
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
		description="NGINX Paasmaker stats log file location. If Paasmaker is managing the nginx, it sets this location automatically.")

	stats_interval = colander.SchemaNode(colander.Integer(),
		title="Stats read interval",
		description="The interval between reading log files, in milliseconds.",
		default=500,
		missing=500)

	nginx = NginxSchema(
		title="Managed NGINX configuration",
		description="The configuration for a managed Nginx that Paasmaker can start for you.",
		missing=NginxSchema.default(),
		default=NginxSchema.default()
	)

	@staticmethod
	def default():
		return {
			'enabled': False,
			'nginx': NginxSchema.default()
		}

class RedisSchema(StrictAboutExtraKeysColanderMappingSchema):
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

class MiscPortsSchema(StrictAboutExtraKeysColanderMappingSchema):
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

class MasterSchema(StrictAboutExtraKeysColanderMappingSchema):
	host = colander.SchemaNode(colander.String(),
		title="Master Node",
		description="The master node for this cluster.")
	port = colander.SchemaNode(colander.Integer(),
		title="Master Node HTTP port",
		description="The master node HTTP port for API requests.",
		default=DEFAULT_API_PORT,
		missing=DEFAULT_API_PORT)

	@staticmethod
	def default():
		return {'host': 'localhost', 'port': DEFAULT_API_PORT, 'isitme': False}

class ConfigurationSchema(StrictAboutExtraKeysColanderMappingSchema):
	http_port = colander.SchemaNode(colander.Integer(),
		title="HTTP Port",
		description="The HTTP port that this node listens on for API requests",
		missing=DEFAULT_API_PORT,
		default=DEFAULT_API_PORT)

	https_port = colander.SchemaNode(
		colander.Integer(),
		title="HTTPS Port",
		description="The HTTPS port that this node listens on for API requests. To enable, you must set this to a port and also set ssl_key and ssl_cert options.",
		missing=None,
		default=None
	)

	ssl_options = colander.SchemaNode(
		colander.Mapping(unknown='preserve'),
		title="SSL options",
		description="The SSL options if SSL is enabled. You need at least `keyfile` and `certfile`. You can put any other options in here from http://docs.python.org/2/library/ssl.html#ssl.wrap_socket",
		missing={},
		default={}
	)

	misc_ports = MiscPortsSchema(
		title="Misc Ports",
		description="The range of ports allocated to application instances or other times where a free port is required.",
		default=MiscPortsSchema.default(),
		missing=MiscPortsSchema.default()
	)

	default_plugins = colander.SchemaNode(colander.Boolean(),
		title="Set up default plugins",
		description="If true, sets up a set of internal plugins for job handling and other tasks. If you turn this off, you will have full control over all plugins - and will need to include job plugins. The default plugins are read from paasmaker/data/defaults/plugins.yml.",
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

	cluster_name = colander.SchemaNode(
		colander.String(),
		title="Friendly Cluster name",
		description="The friendly cluster name presented to users when they log in, and also in page titles to identify this cluster.",
		missing=None,
		default=None
	)

	node_token = colander.SchemaNode(colander.String(),
		title="Node Authentication Token",
		description="Token used by nodes to validate each other. All nodes should have the same token")

	log_directory = colander.SchemaNode(colander.String(),
		title="Log Directory",
		description="Directory used to store log files. If set to None, it will choose a path automatically.",
		# None here means to automatically figure out/generate the path.
		default=None,
		missing=None)

	server_log_level = colander.SchemaNode(colander.String(),
		title="Server log level",
		description="The log level for the server log file. One of DEBUG, INFO, WARNING, ERROR, or CRITICAL. DEBUG is particularly noisy.",
		default="INFO",
		missing="INFO")

	scratch_directory = colander.SchemaNode(colander.String(),
		title="Scratch Directory",
		description="Directory used for data storage. Instances are stored here, as well as run time configuration, managed daemon files and data. This should be a persistent location.",
		default="scratch",
		missing="scratch")

	pid_path = colander.SchemaNode(colander.String(),
		title="PID path",
		description="The path at which to write the PID file.",
		default="paasmaker.pid",
		missing="paasmaker.pid")

	master = MasterSchema(
		title="Master Node details",
		description="Connection information for the master node.",
		default=MasterSchema.default(),
		missing=MasterSchema.default()
	)

	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes. Applications are passed these tags as well, so you will want to be careful what you put in here.",
		missing={},
		default={})

	node_report_interval = colander.SchemaNode(colander.Integer(),
		title="Node report interval",
		description="How long in milliseconds between reports back to the master node. Default is 60 seconds.",
		default=60000,
		missing=60000)

	job_manager_check_interval = colander.SchemaNode(
		colander.Integer(),
		title="Job Manager check interval",
		description="How often, in milliseconds, between checks of the job manager backend to ensure it's still connected.",
		default=5000,
		missing=5000
	)

	pacemaker = PacemakerSchema(
		title="Pacemaker configuration",
		description="The configuration options for the Pacemaker, if enabled.",
		default=PacemakerSchema.default(),
		missing=PacemakerSchema.default()
	)
	heart = HeartSchema(
		title="Heart configuration",
		description="The configuration options for the heart, if enabled.",
		default=HeartSchema.default(),
		missing=HeartSchema.default()
	)
	router = RouterSchema(
		title="Router configuration",
		description="The configuration options for the router, if enabled.",
		default=RouterSchema.default(),
		missing=RouterSchema.default()
	)

	redis = RedisSchema(
		title="Redis configuration",
		description="A complete set of information on how to connect to Redis instances. If omitted, defaults to a fully managed single node configuration.",
		default=RedisSchema.default(),
		missing=RedisSchema.default()
	)

	plugins = PluginsSchema(
		title="Plugins",
		description="A list of plugins registered on this node. It's up to you to make sure they're applicable for this node type.",
		missing=[],
		default=[])

	periodics = PeriodicsSchema(
		title="Periodic tasks",
		description="A list of periodic tasks to run on this node.",
		missing=[],
		default=[]
	)

	default_periodics = colander.SchemaNode(colander.Boolean(),
		title="Include default periodics",
		description="If true, use the default periodics. These are merged with any periodics that you supply.",
		missing=True,
		default=True
	)

	# Server related configuration. This is for an Ubuntu server, set up as
	# per the installation instructions. Obviously, for other platforms
	# this will need to be altered.
	redis_binary = colander.SchemaNode(colander.String(),
		title = "Redis server binary",
		description = "The full path to the redis server binary.",
		default = find_executable("redis-server"),
		missing = find_executable("redis-server"))
	nginx_binary =colander.SchemaNode(colander.String(),
		title="nginx server binary",
		description="The full path to the nginx server binary.",
		default="/usr/local/openresty/nginx/sbin/nginx",
		missing="/usr/local/openresty/nginx/sbin/nginx")

class PluginsOnlySchema(StrictAboutExtraKeysColanderMappingSchema):
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

class ThreadedDatabaseSessionFetcher(paasmaker.util.threadcallback.ThreadCallback):
	"""
	Helper class to grab a SQLalchemy session in another thread, in
	case it blocks waiting on connection or external resources.
	"""

	def _work(self, sessionmaker):
		logger.debug("Creating database session (or waiting for one).")
		session = sessionmaker()
		logger.debug("Got database session, returning to caller.")
		self._callback(session)

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
	def __init__(self, io_loop=None, debug=False):
		super(Configuration, self).__init__(ConfigurationSchema())
		self.port_allocator = paasmaker.util.port.FreePortFinder()
		self.plugins = paasmaker.util.PluginRegistry(self)
		self.uuid = None
		self.job_watcher = None
		self.job_manager = paasmaker.common.job.manager.manager.JobManager(self)
		self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
		self.start_time = datetime.datetime.utcnow()
		self.node_logging_configured = False
		self.database_sessions_checked_out = 0
		self.database_sessions_checkout_pending = 0

		self.redis_scripts = {}

		# Debug flag handling.
		self.debug = debug
		if options.debug == 1:
			self.debug = True

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

		if self['https_port'] is not None:
			# Make sure the keyfile and certfile are set.
			if not 'keyfile' in self['ssl_options'] or not 'certfile' in self['ssl_options']:
				raise InvalidConfigurationParameterException('keyfile and certfile must both be set if you enable listening on an SSL port. Set them inside the ``ssl_options`` mapping.')

		# Convert the scratch directory into a fully qualified path.
		self['scratch_directory'] = os.path.abspath(self['scratch_directory'])

		# Now make sure it exists.
		if not os.path.exists(self['scratch_directory']):
			# Attempt to create it.
			try:
				os.mkdir(self['scratch_directory'])
			except OSError, ex:
				raise InvalidConfigurationParameterException("Scratch directory %s does not exist, and we were unable to create it: %s" % (self['scratch_directory'], str(ex)))

		# Check the logs dir.
		if self['log_directory'] is None:
			self['log_directory'] = os.path.join(self['scratch_directory'], 'logs')

		if not os.path.exists(self['log_directory']):
			# Attempt to create it.
			try:
				os.mkdir(self['log_directory'])
			except OSError, ex:
				raise InvalidConfigurationParameterException("Logs directory %s does not exist, and we were unable to create it: %s" % (self['log_directory'], str(ex)))

		if self['heart']['enabled']:
			if self['heart']['working_dir'] is None:
				self['heart']['working_dir'] = os.path.join(self['scratch_directory'], 'instances')

			if not os.path.exists(self['heart']['working_dir']):
				# Attempt to create it.
				try:
					os.mkdir(self['heart']['working_dir'])
				except OSError, ex:
					raise InvalidConfigurationParameterException("Heart working directory %s does not exist, and we were unable to create it: %s" % (self['log_directory'], str(ex)))

		if self['my_name'] is None:
			self['my_name'] = os.uname()[1]
		if self['my_route'] is None:
			# TODO: improve this detection and use.
			self['my_route'] = socket.getfqdn()

			if '.in-addr.arpa' in self['my_route']:
				# Sometimes on OSX this gives the wrong address; and gives you
				# a reverse resolve. Use localhost instead.
				self['my_route'] = 'localhost'

		# Update the flat representation again before proceeding.
		self.update_flat()

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

		if self.get_flat('default_periodics'):
			# Load the default periodics plugins. We merge these with the others.
			default_file = os.path.join(default_path, 'periodics.yml')
			default_periodics_raw = open(default_file, 'r').read()
			default_periodics_parsed = yaml.safe_load(default_periodics_raw)

			default_periodics_ready = PeriodicsOnlySchema().deserialize(default_periodics_parsed)

			self['periodics'].extend(default_periodics_ready['periodics'])

		# Plugins. Note that we load these after the defaults,
		# so you can re-register the defaults with different options.
		self.load_plugins(self.plugins, self['plugins'])

		# Check SCM lister entries.
		if self.is_pacemaker():
			for meta in self['pacemaker']['scmlisters']:
				if not self.plugins.exists(meta['for'], paasmaker.util.plugin.MODE.SCM_EXPORT):
					raise InvalidConfigurationParameterException("SCM lister entry refers to SCM plugin %s that doesn't exist." % meta['for'])
				for listplugin in meta['plugins']:
					if not self.plugins.exists(listplugin, paasmaker.util.plugin.MODE.SCM_LIST):
						raise InvalidConfigurationParameterException("SCM lister plugin %s doesn't exist (in list for SCM %s)." % (listplugin, meta['for']))

		# Check that the health manager plugins exist.
		# And also that their parameters validate.
		if self.is_pacemaker():
			for group in self['pacemaker']['health']['groups']:
				for plugin in group['plugins']:
					if not self.plugins.exists(plugin['plugin'], paasmaker.util.plugin.MODE.HEALTH_CHECK):
						raise InvalidConfigurationParameterException("Health check plugin %s doesn't exist." % plugin['plugin'])

					# Try to instantiate it with the parameters.
					# This will raise an exception if it's wrong.
					try:
						instance = self.plugins.instantiate(
							plugin['plugin'],
							paasmaker.util.plugin.MODE.HEALTH_CHECK,
							plugin['parameters']
						)
					except InvalidConfigurationFormatException, ex:
						logger.error("Exception: ", exc_info=ex)
						raise InvalidConfigurationParameterException("Error in health check plugin %s parameters. See above." % plugin['plugin'])

		# Check that the periodic plugins exist.
		for periodic in self['periodics']:
			if not self.plugins.exists(periodic['plugin'], paasmaker.util.plugin.MODE.PERIODIC):
				raise InvalidConfigurationParameterException("Periodic plugin %s doesn't exist." % periodic['plugin'])

		# Make sure at least one stats plugin is registered.
		if self.plugins.plugins_for(paasmaker.util.plugin.MODE.NODE_STATS) == 0:
			raise InvalidConfigurationParameterException("No NODE_STATS plugins are registered. Paasmaker can't calculate node scores without that.")

		# Make sure at least one score plugin is registered.
		if self.plugins.plugins_for(paasmaker.util.plugin.MODE.NODE_SCORE) == 0:
			raise InvalidConfigurationParameterException("No NODE_SCORE plugins are registered. Paasmaker can't calculate node scores without that.")

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

	def get_runtimes(self, callback):
		"""
		Get a list of runtimes and their associated versions.

		Once the list is generated, it is cached for the lifetime
		of the server. Subsequent calls return the same list generated
		the first time.

		The callback is called with a dict. The keys are the runtime
		names, and the values are lists of versions that this node
		can run.
		"""
		if not self.is_heart() and not self.is_pacemaker():
			raise ImNotAHeart("I'm not a heart or pacemaker, so I have no runtimes.")

		# Use a cached version if present.
		# The idea is that we don't do this expensive version determination each
		# time we re-register with the master.
		if hasattr(self, '_runtime_cache'):
			logger.debug("Using existing runtime cache.")
			callback(self._runtime_cache)
			return
		else:
			logger.info("Generating runtime list...")

		tags = {}
		runtime_plugins = self.plugins.plugins_for(paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)

		def get_versions():
			try:
				def got_versions(versions):
					if len(versions) > 0:
						# Only report that we have this runtime at all if we have
						# more than one version.
						tags[plugin] = versions

					# Move onto the next plugin.
					get_versions()

					# end of got_versions()

				plugin = runtime_plugins.pop()
				runtime = self.plugins.instantiate(
					plugin,
					paasmaker.util.plugin.MODE.RUNTIME_VERSIONS
				)
				runtime.get_versions(got_versions)

			except IndexError, ex:
				# No more to process.
				# Send back the tags.
				self._runtime_cache = tags
				callback(self._runtime_cache)

			# end of get_versions()

		# Kick off the process.
		get_versions()

	def get_dynamic_tags(self, callback):
		"""
		Get a list of dynamic tags and their associated values.

		This reaches out to plugins to generate the tags. Once run
		the first time, this is not run again until the node restarts.
		"""

		if hasattr(self, '_dynamic_tags_cache'):
			logger.debug("Using existing dynamic tags cache.")
			callback(self._dynamic_tags_cache)
			return
		else:
			logger.info("Generating dynamic tags...")

		dynamic_tags = copy.deepcopy(self['tags'])
		tags_plugins = self.plugins.plugins_for(
			paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS
		)

		def get_tags():
			try:
				def got_tags(tags):
					# Move onto the next plugin.
					get_tags()

					# end of got_tags()

				plugin = tags_plugins.pop()
				tagger = self.plugins.instantiate(
					plugin,
					paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS
				)
				tagger.fetch(dynamic_tags, got_tags)

			except IndexError, ex:
				# No more to process.
				# Send back the tags.
				self._dynamic_tags_cache = dynamic_tags
				callback(self._dynamic_tags_cache)

			# end of get_tags()

		# Kick off the process.
		get_tags()

	def get_node_stats(self, callback):
		"""
		Get a set of stats for the node. This can call out to
		plugins to generate the stats. Once complete, it will call
		the callback with the generated stats.
		"""
		stats = {}

		stats_plugins = self.plugins.plugins_for(
			paasmaker.util.plugin.MODE.NODE_STATS
		)

		def get_stats():
			try:
				def got_stats(stats):
					# Move onto the next plugin.
					get_stats()

					# end of got_stats()

				plugin = stats_plugins.pop()
				stat_collector = self.plugins.instantiate(
					plugin,
					paasmaker.util.plugin.MODE.NODE_STATS
				)
				stat_collector.stats(stats, got_stats)

			except IndexError, ex:
				# No more to process.
				callback(stats)

			# end of get_stats()

		# Kick off the process.
		get_stats()

	def get_node_score(self, stats):
		"""
		Generate a score for this node. This can call out to a set of
		plugins, and the highest score from the plugins is used (as the
		order of execution of plugins is not defined).

		:arg dict stats: The node's stats.
		"""
		scores = []
		score_plugins = self.plugins.plugins_for(
			paasmaker.util.plugin.MODE.NODE_SCORE
		)
		for plugin in score_plugins:
			instance = self.plugins.instantiate(
				plugin,
				paasmaker.util.plugin.MODE.NODE_SCORE
			)
			scores.append(instance.score(stats))

		if len(scores) == 0:
			# No score plugins.
			# Should not be possible, as it's checked on startup.
			# Give the node a high score, as it's misconfigured.
			scores.append(1.0)

		return max(scores)

	def setup_database(self):
		"""
		Set up the database; creating tables on the first startup,
		or otherwise doing nothing on subsequent operations.
		"""
		if not self.is_pacemaker():
			raise ImNotAPacemaker("I'm not a pacemaker, so I have no database.")

		# Connect.
		self.engine = create_engine(self.get_flat('pacemaker.dsn'), **self['pacemaker']['database_options'])
		self.session = sessionmaker(bind=self.engine)

		# Bind the session to the metadata.
		paasmaker.model.Base.metadata.bind = self.engine

		# Now see if we need to create tables. If so, do that,
		# and set the Alembic migrations starting point.
		check_session = None
		try:
			check_session = self.session()
			query = check_session.query(
				func.count(paasmaker.model.Workspace.id)
			)

			# This will throw an exception if the table
			# does not exist. We query Workspace because
			# it exists in the oldest versions of Paasmaker,
			# and additionally it shouldn't contain too
			# many entries.
			count = query.count()

			logger.info("Database already created. No action to take.")

		except sqlalchemy.exc.OperationalError, ex:
			# We need to create the tables. Do that now.
			logger.info("No database created. Creating tables now...")
			paasmaker.model.Base.metadata.create_all()

			# A hack to prevent alembic from altering the
			# Python logger settings.
			paasmaker.ALEMBIC_NO_LOGGING = True

			# And tell alembic to stamp this database at the head
			# migration, for future compatibility.
			from alembic.config import Config
			from alembic import command
			alembic_cfg = Config("alembic.ini")
			command.stamp(alembic_cfg, "head")

	def get_free_port(self):
		"""
		Get a free TCP port in the misc ports range.
		"""
		return self.port_allocator.free_in_range(self.get_flat('misc_ports.minimum'), self.get_flat('misc_ports.maximum'))

	def get_database_session(self, callback, error_callback):
		"""
		Get a database session object. Each requesthandler should fetch
		one of these when it needs to, but hang onto it - repeated
		calls will fetch new sessions every time.

		In production, it was discovered that SQLalchemy will pool these
		for performance, which is what we want, but block when the pool
		is already checked out. For that reason, we push the checkout
		from the pool onto a thread, and callback the caller when the
		session is available.
		"""
		if not self.is_pacemaker():
			raise ImNotA("I'm not a pacemaker, so I have no database.")

		debug_source_traceback = None
		if self.debug:
			debug_source_traceback = traceback.extract_stack()

		def attach_tracker(session):
			self.database_sessions_checkout_pending -= 1
			self.database_sessions_checked_out += 1
			if self.debug:
				if not hasattr(self, '_session_close_tracker'):
					self._session_close_tracker = {}

				# Track sessions to make sure they get closed.
				# This is very hackish, and thus only enabled in debug mode.
				session_key = str(session)

				session.original_close = session.close

				def tracking_close():
					self.database_sessions_checked_out -= 1
					logger.debug(
						"Returning database session. %d pending, %d out.",
						self.database_sessions_checkout_pending,
						self.database_sessions_checked_out
					)
					if session_key in self._session_close_tracker:
						self.io_loop.remove_timeout(self._session_close_tracker[session_key]['timeout'])
						del self._session_close_tracker[session_key]
					session.original_close()

				def session_timeout():
					if session_key in self._session_close_tracker:
						print "Session not closed after 20 seconds."
						print "Opened here:"
						print "".join(traceback.format_list(self._session_close_tracker[session_key]['traceback']))
						del self._session_close_tracker[session_key]

				session.close = tracking_close
				self._session_close_tracker[session_key] = {
					'timeout': self.io_loop.add_timeout(time.time() + 20, session_timeout),
					'traceback': debug_source_traceback
				}

			callback(session)

		def attach_lightweight_counter(session):
			self.database_sessions_checkout_pending -= 1
			self.database_sessions_checked_out += 1
			session.original_close = session.close

			def counter_decrement():
				self.database_sessions_checked_out -= 1
				logger.debug(
					"Returning database session. %d pending, %d out.",
					self.database_sessions_checkout_pending,
					self.database_sessions_checked_out
				)
				session.original_close()

			session.close = counter_decrement

			callback(session)

		# Figure out which callback to go back through.
		real_callback = attach_lightweight_counter

		if self.debug:
			real_callback = attach_tracker

		logger.debug(
			"Fetch database session. %d pending, %d out.",
			self.database_sessions_checkout_pending,
			self.database_sessions_checked_out
		)

		self.database_sessions_checkout_pending += 1

		fetcher = ThreadedDatabaseSessionFetcher(self.io_loop, real_callback, error_callback)
		fetcher.work(self.session)

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
		client = TornadoRedisClient(
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
			if not meta_key in self.redis_meta:
				self.redis_meta[meta_key] = {
					'state': 'CREATE',
					'queue': [],
					'shutdown': credentials['shutdown']
				}

			meta = self.redis_meta[meta_key]

			# Callback to handle when it's up and running.
			def on_redis_started(message):
				# Mark it as started.
				meta['state'] = 'STARTED'

				# Play back all our callbacks.
				for queued in meta['queue']:
					self._connect_redis(queued[0], queued[1], queued[2])

				# Is this a router table, that's a slave of another?
				if name == 'table':
					# TODO: Ensure this retries if it fails on first startup.
					if self.get_flat('redis.slaveof.enabled'):
						def on_slaved(result):
							logger.info("Successfully set up redis server as slave of the master.")
							logger.debug("%s", str(result))

						def got_redis(client):
							# TODO: Does not support password protected Redis instances!
							client.execute_command(
								'SLAVEOF',
								self.get_flat('redis.slaveof.host'),
								self.get_flat('redis.slaveof.port'),
								callback=on_slaved
							)

						def failed_redis(message, exception=None):
							# Nope. TODO: Take some other action?
							logger.error("Unable to get redis to make into slave: %s", message)
							if exception:
								logger.error("Exception:", exc_info=exception)

						# It's a slave. Make it so.
						self._connect_redis(credentials, got_redis, failed_redis)

			def on_redis_startup_failure(message, exception=None):
				error_message = "Failed to start managed redis for %s: %s" % (name, message)
				logger.error(error_message)
				if exception:
					logger.error("Exception:", exc_info=exception)
				error_callback(error_message)

			# Change the action based on our state.
			if meta['state'] == 'CREATE':
				# This is the first attempt to access it.
				# Start up the service.
				meta['state'] = 'STARTING'
				meta['queue'].append((credentials, callback, error_callback))

				def redis_configured(message):
					logger.debug("Starting redis for %s", name)
					meta['manager'].start_if_not_running(on_redis_started, on_redis_startup_failure)

				directory = self.get_scratch_path_exists(
					'redis', name
				)
				meta['manager'] = paasmaker.util.redisdaemon.RedisDaemon(self)
				try:
					meta['manager'].load_parameters(directory)

					redis_configured("Configured")
				except paasmaker.util.ManagedDaemonError, ex:
					# Doesn't yet exist. Create it.
					logger.debug("Creating redis for %s", name)
					meta['manager'].configure(
						directory,
						credentials['port'],
						credentials['host'],
						redis_configured,
						error_callback,
						password=credentials['password']
					)

			elif meta['state'] == 'STARTING':
				# Queue up our callbacks.
				meta['queue'].append((credentials, callback, error_callback))
			else:
				# Must be started. Just connect.
				if not meta['manager'].is_running():
					meta['state'] = 'CREATE'
					# Call this function again to go through.
					self._get_redis(name, credentials, callback, error_callback)
				else:
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

	def shutdown_managed_redis(self, callback, error_callback):
		"""
		Shutdown any managed redis instances for which we've been
		configured to shutdown on exit.

		This has no action if no Redis instances have been configured
		to shutdown on exit.
		"""
		if hasattr(self, 'redis_meta'):
			iterator = self.redis_meta.iteritems()

			def next_item(message=''):
				try:
					iterator_meta = iterator.next()
					key = iterator_meta[0]
					meta = iterator_meta[1]

					if meta['state'] == 'STARTED' and meta['shutdown']:
						logger.info("Shutting down managed redis, because requested to do so.")
						meta['manager'].stop(next_item, error_callback)
					else:
						# Jump to the next item.
						next_item()

				except StopIteration, ex:
					# No more to process.
					callback("Shut down all redis instances.")

			self.job_manager.shutdown(next_item, error_callback)
		else:
			callback("No managed Redis instances to shutdown.")

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
		settings['debug'] = self.debug
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
		self.job_manager.watchdog.enable()

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

	def startup_periodic_manager(self, start_checking=True):
		"""
		Set up the periodic manager.

		This should be called on startup to set up the periodic manager.

		:arg bool start_checking: If True, start checking according
			to the configured schedule. This parameter is intended for
			unit tests, to disable the default behaviour.
		"""
		self.periodic_manager = paasmaker.common.helper.periodicmanager.PeriodicManager(self)

		if start_checking:
			self.periodic_manager.start()

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

	def locate_log(self, job_id, callback, error_callback, unittest_force_remote=False):
		"""
		Locate the log file given by the job_id. Calls the callback
		with two arguments. The first argument is the job ID. The second
		argument is one of the following:

		* A string, which is the path to the log file.
		* A Node ORM object, that indicates where the file is. This will
		  only be returned on Pacemaker nodes (as other nodes do not have
		  access to the database). The session attached to it will be closed,
		  so you won't be able to follow references.

		:arg str job_id: The job ID to search for (which could also be
			an instance ID or node UUID).
		:arg callable callback: The callback to call when the job is found.
		:arg callable error_callback: The error callback for when the log
			can't be found, or the remote is down.
		"""
		# Try the easy case - does the log exist here?
		if self.job_exists_locally(job_id) and not unittest_force_remote:
			# Yep. Done.
			callback(job_id, self.get_job_log_path(job_id))
			return

		if not self.job_exists_locally(job_id) and not self.is_pacemaker():
			# It doesn't exist locally - which can be caused by the
			# job not yet starting. Seeing as we're not a Pacemaker, act like
			# it does exist, in the expectation that it'll come through shortly.
			# We assume you only got here if you're a pacemaker which should
			# limit the number of invalid job requests.
			callback(job_id, self.get_job_log_path(job_id))
			return

		def got_database_session(session):
			# Now move onto the synchronous tests.
			# TODO: This queries the DB twice for each lookup, which
			# can be expensive. Having said that, tailing a log isn't something
			# that's done that often. Discuss.
			# Is the job_id an instance log?
			instance = session.query(
				paasmaker.model.ApplicationInstance
			).filter(
				paasmaker.model.ApplicationInstance.instance_id == job_id
			).first()

			def check_node(node):
				# Helper function to check the given node and return.
				session.close()
				if node is None:
					error_callback(job_id, "Can't find a node with this job on it.")
					return
				elif node.state == constants.NODE.ACTIVE:
					callback(job_id, node)
				else:
					error_callback(job_id, "Node %s has the log file, but that node is down." % node.name)

			if instance is not None:
				# It's on the given remote node.
				# If the node is working...
				check_node(instance.node)
				return

			# Try again - see if it's a node.
			node = session.query(
				paasmaker.model.Node
			).filter(
				paasmaker.model.Node.uuid == job_id
			).first()

			if node is not None:
				# It's the given remote node.
				check_node(node)
				return

			# Now, check the jobs system to see where that node is.
			def on_got_job(data):
				logger.debug("Got job metata for %s", job_id)
				if not data.has_key(job_id):
					error_callback(job_id, "No such job %s." % job_id)
				else:
					# Locate the node that it's on.
					node = session.query(
						paasmaker.model.Node
					).filter(
						paasmaker.model.Node.uuid == data[job_id]['node']
					).first()

					# And pass it back.
					check_node(node)

			self.job_manager.get_jobs([job_id], on_got_job)

			# end of got_database_session()

		self.get_database_session(got_database_session, error_callback)

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

	def setup_node_logging(self):
		if not self.node_logging_configured:
			if self.get_node_uuid():
				# Redirect log output into a file based on the node UUID.
				node_log_path = self.get_job_log_path(self.get_node_uuid())
				root_logger = logging.getLogger()
				log_handler = logging.FileHandler(node_log_path)
				log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
				root_logger.addHandler(log_handler)
				self.node_logging_configured = True

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

		# The islink check is for development directory instances.
		# Because if they point to an invalid location, os.path.exists() returns False,
		# which makes it try to create the directory, which fails because it's a symlink.
		if not os.path.islink(path) and not os.path.exists(path):
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
master:
  host: localhost
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
		except InvalidConfigurationFormatException, ex:
			self.assertTrue(True, "Configuration did not pass the schema or was invalid.")

	def test_simple_default(self):
		open(self.tempnam, 'w').write(self.minimum_config)
		config = Configuration()
		config.load_from_file([self.tempnam])
		self.assertEqual(config.get_flat('http_port'), DEFAULT_API_PORT, 'No default present.')


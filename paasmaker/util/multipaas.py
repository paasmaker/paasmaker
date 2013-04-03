#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid
import tempfile
import subprocess
import json
import os
import logging
import time
import shutil
import signal

import paasmaker
import yaml

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class MultiPaas(object):
	"""
	Create a miniature Paasmaker cluster on a single machine,
	for testing purposes.

	:arg int port_min: The minimum port for temporary ports.
	:arg int port_max: The maximum port for temporary ports.
	:arg int app_min: The minimum port for applications.
	:arg int app_max: The maximum port for applications.
	"""

	def __init__(self,
			port_min=42800,
			port_max=42899,
			app_min=42900,
			app_max=42999):
		self.cluster_params = {}
		self.nodes = []
		self.port_allocator = paasmaker.util.port.FreePortFinder()
		self.port_min = port_min
		self.port_max = port_max
		self.app_min = app_min
		self.app_max = app_max

		self.cluster_root = tempfile.mkdtemp()

		# Choose some entire cluster parameters.
		self.cluster_params['cluster_root'] = self.cluster_root
		self.cluster_params['node_token'] = str(uuid.uuid4())
		self.cluster_params['super_token'] = str(uuid.uuid4())
		self.cluster_params['cluster_hostname'] = 'local.paasmaker.net'

		# TODO: Allow switching out database backends.
		#database_path = os.path.join(self.cluster_root, 'paasmaker.db')
		#self.cluster_params['dsn'] = "sqlite:///%s" % database_path
		self.cluster_params['dsn'] = "sqlite:///:memory:"

		self.cluster_params['jobs_redis_port'] = self._free_port()
		self.cluster_params['stats_redis_port'] = self._free_port()
		self.cluster_params['router_redis_port'] = self._free_port()

		# Choose a port for the master.
		self.cluster_params['master_port'] = self._free_port()

		if os.path.exists('paasmaker.yml'):
			contents = open('paasmaker.yml', 'r').read()
			parsed = yaml.safe_load(contents)

			self.cluster_params['binaries'] = "redis_binary: %s\nnginx_binary: %s\n" % (parsed['redis_binary'], parsed['nginx_binary'])
		else:
			self.cluster_params['binaries'] = ""

	def _free_port(self):
		return self.port_allocator.free_in_range(self.port_min, self.port_max)

	def add_node(self, pacemaker=False, heart=False, router=False):
		"""
		Add a node to this Multipaas cluster. Call this mulitple
		times to add nodes to the cluster.

		:arg bool pacemaker: If true, this node is a pacemaker.
		:arg bool heart: If true, this node is a heart.
		:arg bool router: If true, this node is a router.
		"""
		unique = str(uuid.uuid4())[0:8]
		node_name = "node_%d_%s" % (len(self.nodes), unique)
		node_port = self._free_port()
		node_dir = os.path.join(self.cluster_root, node_name)
		node_config_path = os.path.join(self.cluster_root, "%s.yml" % node_name)
		os.makedirs(node_dir)

		# Only the first node is the master.
		is_master = (len(self.nodes) == 0)

		node = Paasmaker(pacemaker, heart, router)
		node.choose_parameters(
			self,
			node_dir,
			node_name,
			node_port,
			node_config_path,
			self.cluster_params,
			is_master,
			self.cluster_params['master_port']
		)

		# We don't write the configuration yet - wait until
		# all nodes are added, so we can figure out the correct
		# router to use.

		self.nodes.append(node)

	def start_nodes(self):
		"""
		Start all the nodes that have been added to this cluster.

		If a node fails to start before it forks, this will print
		out the server log file, and then raise an exception.
		"""

		# Figure out the first node with a router, and use
		# that ones direct port as the frontend domain postfix.
		for node in self.nodes:
			if node.router:
				self.cluster_params['frontend_domain_postfix'] = ":%d" % node.params['nginx_port_direct']
				# Stop now.
				break

		# Write out the config files.
		for node in self.nodes:
			node.write_configuration(self.cluster_params, node.node_config_path)

		# And start them up.
		for node in self.nodes:
			try:
				node.start()
			except subprocess.CalledProcessError, ex:
				# Print out the error log.
				print open(node.log_file, 'r').read()
				raise ex

	def stop_nodes(self):
		"""
		Stop all the started nodes. The last node is shut down first,
		on the assumption that the first node is the pacemaker.
		"""
		# Kill off the nodes in reverse order.
		cloned = list(self.nodes)
		cloned.reverse()
		pidlist = []
		for node in cloned:
			pidlist.append(node.stop())

		# Wait until the nodes have finished.
		for pid in pidlist:
			if pid:
				while paasmaker.util.processcheck.ProcessCheck.is_running(pid, 'pm-server'):
					logger.info("Waiting for pid %d to finish.", pid)
					time.sleep(0.1)

		logger.info("All nodes stopped.")

	def destroy(self):
		"""
		Destroy all on disk data for this cluster. It's assumed that the
		cluster is shut down at this stage; otherwise you will have
		difficuly shutting the nodes down after this has been called.
		"""
		logger.info("Destroying all node data...")
		shutil.rmtree(self.cluster_root)

	def get_summary(self):
		"""
		Get a summary of information for this cluster.
		"""
		summary = {}
		summary['configuration'] = self.cluster_params
		summary['nodes'] = []
		for node in self.nodes:
			summary['nodes'].append(node.params)

		return summary

	def get_executor(self):
		"""
		Return a new Executor object pointing to this
		Multipaas cluster. This can be used to execute
		command line commands against the cluster.
		"""
		return Executor(
			'localhost',
			self.cluster_params['master_port'],
			self.cluster_params['super_token']
		)

class Executor(object):
	"""
	A class that allows running commands against the given
	cluster. Designed to allow tests to be written and be
	independant of being a Multipaas or a real test cluster.

	:arg str target_host: The target pacemaker host.
	:arg int target_port: The target pacemaker port.
	:arg str auth_value: The appropriate value for the
		authentication method.
	"""
	def __init__(self, target_host, target_port, auth_value):
		self.target = []
		self.target.extend(['-r', target_host])
		self.target.extend(['-p', str(target_port)])
		self.auth = '--key=' + auth_value

	def run(self, arguments):
		"""
		Run the given command against the cluster.

		This is the equivalent of running
		``./pm-command.py <arguments>`` with suitable
		target and authentication options inserted.

		The supplied arguments are a list. Any argument
		that isn't a string is converted to a string
		using ``str()``.

		The return value is a dict - the JSON decoded
		output of the command. If the command fails,
		it throws an exception.

		:arg list arguments: The argments to pm-command.
		"""
		command_line = []
		# TODO: Figure out the correct path to this command.
		command_line.append('./pm-command.py')
		command_line.extend(arguments)

		command_line.extend(self.target)
		command_line.append(self.auth)

		for i in range(len(command_line)):
			if not isinstance(command_line[i], str):
				command_line[i] = str(command_line[i])

		result = subprocess.check_output(command_line)
		return json.loads(result)

class Paasmaker(object):
	"""
	A class that represents a Paasmaker server, for use
	by the MultiPaas.

	The MultiPaas knows how to instantiate these, so you
	should not typically need to instantiate this class.
	"""

	# TODO: Automatically slaved managed routing table redis.
	COMMON_CONFIGURATION = """
http_port: %(node_port)d
node_token: %(node_token)s
server_log_level: DEBUG
log_directory: %(log_dir)s
scratch_directory: %(scratch_dir)s
pid_path: %(pid_path)s
my_name: %(node_name)s
%(binaries)s
master:
  host: localhost
  port: %(master_port)d

redis:
%(table_redis)s
  stats:
    host: 127.0.0.1
    port: %(stats_redis_port)d
    managed: %(is_cluster_master)s
    shutdown: true
  jobs:
    host: 127.0.0.1
    port: %(jobs_redis_port)d
    managed: %(is_cluster_master)s
    shutdown: true

plugins:
  # SCMs
  - name: paasmaker.scm.zip
    class: paasmaker.pacemaker.scm.zip.ZipSCM
    title: Zip file SCM
  - name: paasmaker.scm.tarball
    class: paasmaker.pacemaker.scm.tarball.TarballSCM
    title: Tarball SCM
  - name: paasmaker.scm.git
    class: paasmaker.pacemaker.scm.git.GitSCM
    title: Git SCM

  # Runtimes
  - name: paasmaker.runtime.shell
    class: paasmaker.heart.runtime.ShellRuntime
    title: Shell Runtime

  - class: paasmaker.heart.runtime.RbenvRuntime
    name: paasmaker.runtime.ruby.rbenv
    parameters:
      rbenv_path: ~/.rbenv
    title: Ruby (rbenv) Runtime

  - class: paasmaker.heart.runtime.nvm.NvmRuntime
    name: paasmaker.runtime.node.nvm
    parameters:
      nvm_path: ~/.nvm
    title: Nodejs (nvm) Runtime

  - class: paasmaker.heart.runtime.php.PHPRuntime
    name: paasmaker.runtime.php
    parameters:
      managed: true
      shutdown: true
    title: PHP Runtime

  - class: paasmaker.heart.runtime.static.StaticRuntime
    name: paasmaker.runtime.static
    parameters:
      managed: true
      shutdown: true
    title: Static Files Runtime

  # Services
  - name: paasmaker.service.parameters
    class: paasmaker.pacemaker.service.parameters.ParametersService
    title: Parameters Service

  - class: paasmaker.pacemaker.service.managedpostgres.ManagedPostgresService
    name: paasmaker.service.postgres
    parameters:
      root_password: paasmaker
      shutdown: true
    title: Managed Postgres Service

  - class: paasmaker.pacemaker.service.managedmysql.ManagedMySQLService
    name: paasmaker.service.mysql
    parameters:
      root_password: paasmaker
      shutdown: true
    title: Managed MySQL service

  - class: paasmaker.pacemaker.service.managedredis.ManagedRedisService
    name: paasmaker.service.managedredis
    parameters:
      shutdown: true
    title: Managed Redis Service
"""

	# TODO: The frontend_domain_postfix command below will fail
	# if the test node isn't a router.
	PACEMAKER = """
pacemaker:
  enabled: true
  super_token: %(super_token)s
  allow_supertoken: true
  cluster_hostname: %(cluster_hostname)s
  dsn: "%(dsn)s"
  frontend_domain_postfix: "%(frontend_domain_postfix)s"
"""

	HEART = """
heart:
  enabled: true
  working_dir: %(heart_working_dir)s
  shutdown_on_exit: true
"""

	ROUTER = """
router:
  enabled: true
  stats_log: managed at runtime
  nginx:
    port_direct: %(nginx_port_direct)d
    port_80: %(nginx_port_80)d
    port_443: %(nginx_port_443)d
    managed: true
    shutdown: true
"""

	MASTER_REDIS = """
  table:
    host: 127.0.0.1
    port: %(router_redis_port)d
    managed: true
    shutdown: true
"""

	SLAVE_REDIS = """
  table:
    host: 127.0.0.1
    port: %(my_slave_redis_port)d
    managed: true
    shutdown: true
  slaveof:
    enabled: true
    host: localhost
    port: %(router_redis_port)d
"""

	def __init__(self, pacemaker, heart, router):
		self.pacemaker = pacemaker
		self.heart = heart
		self.router = router
		self.params = {}
		self.complete_params = {}
		self.config_path = None

	def _exists(self, node_dir, subdir):
		path = os.path.join(node_dir, subdir)
		if not os.path.exists(path):
			os.makedirs(path)
		return path

	def choose_parameters(self,
			multipaas,
			node_dir,
			node_name,
			node_port,
			node_config_path,
			cluster_parameters,
			master=False,
			master_port=None):
		self.params['log_dir'] = self._exists(node_dir, 'logs')
		self.params['scratch_dir'] = self._exists(node_dir, 'scratch')
		self.params['pid_path'] = os.path.join(node_dir, 'node.pid')
		self.params['node_name'] = node_name
		self.node_config_path = node_config_path
		if master:
			self.params['node_port'] = master_port
		else:
			self.params['node_port'] = node_port

		if self.heart:
			self.params['heart_working_dir'] = self._exists(node_dir, 'heart')

		self.params['my_slave_redis_port'] = multipaas._free_port()

		if self.router:
			self.params['nginx_port_direct'] = multipaas._free_port()
			self.params['nginx_port_80'] = multipaas._free_port()
			self.params['nginx_port_443'] = multipaas._free_port()

		if master:
			self.params['is_cluster_master'] = 'true'
		else:
			self.params['is_cluster_master'] = 'false'

	def write_configuration(self, cluster_parameters, output_name):
		# Build up the configuration file.
		raw_configuration = self.COMMON_CONFIGURATION

		if self.pacemaker:
			raw_configuration += self.PACEMAKER

		if self.heart:
			raw_configuration += self.HEART

		if self.router:
			raw_configuration += self.ROUTER


		self.complete_params = dict(cluster_parameters)
		self.complete_params.update(self.params)

		if self.complete_params['is_cluster_master'] == 'true':
			table_redis = self.MASTER_REDIS % self.complete_params
			self.complete_params['table_redis'] = table_redis
		else:
			table_redis = self.SLAVE_REDIS % self.complete_params
			self.complete_params['table_redis'] = table_redis

		merged_configuration = raw_configuration % self.complete_params

		fp = open(output_name, 'w')
		fp.write(merged_configuration)
		fp.close()

		self.config_path = output_name

	def start(self):
		# Start it up, blocking until it starts successfully.
		# We allow it to fork into the background.
		self.log_file = os.path.join(self.complete_params['cluster_root'], "%s.log" % self.params['node_name'])
		log_fp = open(self.log_file, 'w')
		logging.info("Starting node %s...", self.params['node_name'])
		subprocess.check_call(
			[
				'./pm-server.py',
				'--configfile=' + self.config_path
			],
			stdout=log_fp,
			stderr=log_fp
		)
		logging.info("Node %s should be started.", self.params['node_name'])

	def get_pid(self):
		pidfile = self.complete_params['pid_path']
		if os.path.exists(pidfile):
			return int(open(pidfile, 'r').read())
		else:
			return None

	def stop(self):
		# Find the PID.
		pid = self.get_pid()
		if pid:
			# And stop it.
			os.kill(pid, signal.SIGTERM)
			logging.info("Killed node %s.", self.params['node_name'])
		else:
			logging.error("Node %s not running.", self.params['node_name'])

		return pid
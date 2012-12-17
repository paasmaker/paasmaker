
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

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class MultiPaas(object):
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
		database_path = os.path.join(self.cluster_root, 'paasmaker.db')
		self.cluster_params['dsn'] = "sqlite:///%s" % database_path

		self.cluster_params['jobs_redis_port'] = self.free_port()
		self.cluster_params['stats_redis_port'] = self.free_port()
		self.cluster_params['router_redis_port'] = self.free_port()

		# Choose a port for the master.
		self.cluster_params['master_port'] = self.free_port()

	def free_port(self):
		return self.port_allocator.free_in_range(self.port_min, self.port_max)

	def add_node(self, pacemaker=False, heart=False, router=False):
		unique = str(uuid.uuid4())[0:8]
		node_name = "node_%d_%s" % (len(self.nodes), unique)
		node_port = self.free_port()
		node_dir = os.path.join(self.cluster_root, node_name)
		node_config = os.path.join(self.cluster_root, "%s.yml" % node_name)
		os.makedirs(node_dir)

		node = Paasmaker(pacemaker, heart, router)
		node.choose_parameters(
			self,
			node_dir,
			node_name,
			node_port,
			self.cluster_params,
			len(self.nodes) == 0, # Only the first node is the master.
			self.cluster_params['master_port']
		)
		node.write_configuration(self.cluster_params, node_config)

		self.nodes.append(node)

	def start_nodes(self):
		for node in self.nodes:
			node.start()

	def stop_nodes(self):
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
		logger.info("Destroying all node data...")
		shutil.rmtree(self.cluster_root)

	def get_summary(self):
		summary = {}
		summary['configuration'] = self.cluster_params
		summary['nodes'] = []
		for node in self.nodes:
			summary['nodes'].append(node.params)

		return summary

	def get_executor(self):
		return Executor(
			'localhost',
			self.cluster_params['master_port'],
			'super',
			self.cluster_params['super_token']
		)

class Executor(object):
	def __init__(self, target_host, target_port, auth_method, auth_value):
		self.target = []
		self.target.extend(['-r', target_host])
		self.target.extend(['-p', str(target_port)])
		if auth_method == 'super':
			self.auth = '--superkey=' + auth_value

	def run(self, arguments):
		command_line = []
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
	# TODO: Automatically slaved managed routing table redis.
	COMMON_CONFIGURATION = """
http_port: %(node_port)d
node_token: %(node_token)s
server_log_level: DEBUG
log_directory: %(log_dir)s
scratch_directory: %(scratch_dir)s
pid_path: %(pid_path)s
my_name: %(node_name)s
master:
  host: localhost
  port: %(master_port)d
  isitme: %(is_cluster_master)s

redis:
  table:
    host: 127.0.0.1
    port: %(router_redis_port)d
    managed: %(is_cluster_master)s
    shutdown: true
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
  - name: paasmaker.scm.zip
    class: paasmaker.pacemaker.scm.zip.ZipSCM
    title: Zip file SCM
  - name: paasmaker.scm.tarball
    class: paasmaker.pacemaker.scm.tarball.TarballSCM
    title: Tarball SCM
  - name: paasmaker.scm.git
    class: paasmaker.pacemaker.scm.git.GitSCM
    title: Git SCM

  - name: paasmaker.runtime.shell
    class: paasmaker.heart.runtime.ShellRuntime
    title: Shell Runtime

  - name: paasmaker.service.parameters
    class: paasmaker.pacemaker.service.parameters.ParametersService
    title: Parameters Service
"""

	PACEMAKER = """
pacemaker:
  enabled: true
  super_token: %(super_token)s
  allow_supertoken: true
  cluster_hostname: %(cluster_hostname)s
  dsn: %(dsn)s
"""

	HEART = """
heart:
  enabled: true
  working_dir: %(heart_working_dir)s
"""

	ROUTER = """
router:
  enabled: true
  stats_log: managed at runtime
  nginx:
    port: %(nginx_port)d
    managed: true
    shutdown: true
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
			cluster_parameters,
			master=False,
			master_port=None):
		self.params['log_dir'] = self._exists(node_dir, 'logs')
		self.params['scratch_dir'] = self._exists(node_dir, 'scratch')
		self.params['pid_path'] = os.path.join(node_dir, 'node.pid')
		self.params['node_name'] = node_name
		if master:
			self.params['node_port'] = master_port
		else:
			self.params['node_port'] = node_port

		if self.heart:
			self.params['heart_working_dir'] = self._exists(node_dir, 'heart')

		if self.router:
			self.params['nginx_port'] = multipaas.free_port()

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

		merged_configuration = raw_configuration % self.complete_params

		fp = open(output_name, 'w')
		fp.write(merged_configuration)
		fp.close()

		self.config_path = output_name

	def start(self):
		# Start it up, blocking until it starts successfully.
		# We allow it to fork into the background.
		log_file = os.path.join(self.complete_params['cluster_root'], "%s.log" % self.params['node_name'])
		log_fp = open(log_file, 'w')
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
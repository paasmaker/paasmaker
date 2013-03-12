import unittest
import os
import subprocess
import tempfile
import shutil
import signal
import json
import time

import paasmaker

import tornado.testing

# The tests in this file are designed to test the LUA scripts used by the router
# to make it's routing determinations.

class NginxRouter(object):
	"""
	Generate a working NGINX configuration file based on the
	current configuration of Paasmaker.

	It is used by unit tests to generate a test NGINX instance,
	and also by the managed NGINX server.

	This code closely mirrors the design of the managed service plugins.
	"""

	NGINX_CONFIG = """
worker_processes 1;
error_log %(log_path)s/error.log %(log_level)s;
pid %(pid_path)s/nginx.pid;

events {
	worker_connections  256;
}

http {
	log_format paasmaker '{"version_type_key":"$versiontypekey","node_key":"$nodekey","instance_key":"$instancekey",'
		'"bytes":$bytes_sent,"code":$status,"upstream_response_time":"$upstream_response_time",'
		'"time":"$time_iso8601","timemsec":$msec,"nginx_response_time":$request_time}';

	access_log %(log_path)s/access.log.paasmaker paasmaker;
	access_log %(log_path)s/access.log combined;

	%(temp_paths)s

	server {
		listen       [::]:%(listen_port_direct)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
			set $versiontypekey "null";
			set $nodekey "null";
			set $instancekey "null";
			rewrite_by_lua_file %(router_root)s/rewrite.lua;

			proxy_set_header            Host $host;
			proxy_buffering             off;
			proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header            X-Forwarded-Port $server_port;
			proxy_set_header            X-Forwarded-Host $host;
			proxy_redirect              off;
			proxy_connect_timeout       10;
			proxy_send_timeout          60;
			proxy_read_timeout          60;
			proxy_pass                  http://$upstream;
		}
	}

	server {
		listen       [::]:%(listen_port_80)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
			set $versiontypekey "null";
			set $nodekey "null";
			set $instancekey "null";
			rewrite_by_lua_file %(router_root)s/rewrite.lua;

			proxy_set_header            Host $host;
			proxy_buffering             off;
			proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header            X-Forwarded-Port 80;
			proxy_set_header            X-Forwarded-Host $host;
			proxy_redirect              off;
			proxy_connect_timeout       10;
			proxy_send_timeout          60;
			proxy_read_timeout          60;
			proxy_pass                  http://$upstream;
		}
	}

	server {
		listen       [::]:%(listen_port_443)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
			set $versiontypekey "null";
			set $nodekey "null";
			set $instancekey "null";
			rewrite_by_lua_file %(router_root)s/rewrite.lua;

			proxy_set_header            Host $host;
			proxy_buffering             off;
			proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header            X-Forwarded-Port 443;
			proxy_set_header            X-Forwarded-Host $host;
			proxy_set_header            X-Forwarded-Proto https;
			proxy_redirect              off;
			proxy_connect_timeout       10;
			proxy_send_timeout          60;
			proxy_read_timeout          60;
			proxy_pass                  http://$upstream;
		}
	}
}
"""

	TEMP_PATHS = """
	client_body_temp_path %(temp_dir)s/;
	proxy_temp_path %(temp_dir)s/;
	fastcgi_temp_path %(temp_dir)s/;
	uwsgi_temp_path %(temp_dir)s/;
	scgi_temp_path %(temp_dir)s/;
	"""

	def __init__(self, configuration):
		self.configuration = configuration

	def startup(self, callback, error_callback):
		daemon = paasmaker.util.nginxdaemon.NginxDaemon(self.configuration)

		working_dir = self.configuration.get_scratch_path_exists('nginx')

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		# And create a directory for temp files.
		temp_file_dir = os.path.join(working_dir, 'temp')
		if not os.path.exists(temp_file_dir):
			os.makedirs(temp_file_dir)

		parameters = {}
		parameters['port_direct'] = self.configuration.get_flat('router.nginx.port_direct')
		parameters['port_80'] = self.configuration.get_flat('router.nginx.port_80')
		parameters['port_443'] = self.configuration.get_flat('router.nginx.port_443')
		parameters['temp_path'] = temp_file_dir
		parameters['pid_path'] = working_dir
		parameters['log_level'] = 'info'
		parameters['log_path'] = working_dir

		self.generated_config = self.get_nginx_config(
			self.configuration, managed_params=parameters
		)

		try:
			daemon.load_parameters(working_dir)
		except paasmaker.util.ManagedDaemonError, ex:
			# Doesn't yet exist. Create it.
			daemon.configure(
				working_dir,
				parameters['port_direct'],
				self.generated_config['configuration']
			)

		def on_nginx_started(message):
			# Set the stats log path manually.
			self.configuration['router']['stats_log'] = os.path.join(working_dir, 'access.log.paasmaker')
			self.configuration.update_flat()

			# And let the caller know we're ready.
			callback(message)

		def on_nginx_failed(message):
			error_message = "Unable to start managed NGINX router component: %s" % message
			error_callback(error_message)

		daemon.start_if_not_running(on_nginx_started, on_nginx_failed)

	def get_configuration(self):
		return self.generated_config

	def shutdown(self):
		"""
		If configured, shutdown an associated managed NGINX instance
		on exit. TODO: take callbacks
		"""
		if self.configuration.get_flat('router.nginx.managed') and self.configuration.get_flat('router.nginx.shutdown'):
			daemon = paasmaker.util.nginxdaemon.NginxDaemon(self.configuration)
			working_dir = self.configuration.get_scratch_path_exists('nginx')

			try:
				daemon.load_parameters(working_dir)
				if daemon.is_running():
					daemon.stop()
			except paasmaker.util.ManagedDaemonError, ex:
				# No daemon is running, so nothing to do
				pass

	def get_nginx_config(self, configuration, managed_params):
		"""
		Create and return a NGINX configuration file based on
		the supplied configuration object.

		If you supply a dict for managed_params, it should
		have the following keys:

		* temp_path: The path to temporary files.
		* port: The TCP port to listen on.
		* log_path: The path to place log files at.
		* pid_path: The full path to the pid.
		* log_level: The NGINX error log level.

		The return value is a dict, containing the following
		keys:

		* configuration: a string containing the NGINX
		  configuration.
		* temp_dir: The temporary directory for NGINX.
		* listen_port_direct: The port that the NGINX server will
		  listen on for direct connections.
		* listen_port_80: The port that the NGINX server will
		  listen on for port 80 connections.
		* listen_port_443: The port that the NGINX server will
		  listen on for port 443 connections.
		* log_path: The path where log files will be placed.
		* pid_path: The full path to the NGINX server PID.
		* log_level: The NGINX log level.
		* router_root: The path where the router LUA files
		  are stored.

		:arg Configuration configuration: The configuration
			object to read from.
		:arg dict|None managed_params: If this is a managed
			NGINX service, the values in this dict control
			some variables in the output configuration.
		"""
		parameters = {}

		parameters['temp_dir'] = managed_params['temp_path']
		parameters['listen_port_direct'] = managed_params['port_direct']
		parameters['listen_port_80'] = managed_params['port_80']
		parameters['listen_port_443'] = managed_params['port_443']
		parameters['log_path'] = managed_params['log_path']
		parameters['temp_paths'] = NginxRouter.TEMP_PATHS % {'temp_dir': managed_params['temp_path']}
		parameters['pid_path'] = managed_params['pid_path']
		parameters['log_level'] = managed_params['log_level']

		parameters['redis_host'] = configuration.get_flat('redis.table.host')
		parameters['redis_port'] = configuration.get_flat('redis.table.port')

		# This is where the LUA files are stored.
		parameters['router_root'] = os.path.normpath(os.path.dirname(__file__))

		configuration = NginxRouter.NGINX_CONFIG % parameters

		parameters['configuration'] = configuration

		return parameters

class RouterTest(paasmaker.common.controller.base.BaseControllerTest):
	"""
	Test the NGINX routing system and stats collector.

	This unit test starts up a NGINX server and matching Redis
	server, connecting them together. It then tests that the router
	lookups work correctly.

	After that, it tests that the stats reader can read
	the resulting log files.
	"""

	config_modules = ['pacemaker', 'router']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = paasmaker.common.controller.example.ExampleController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.common.controller.example.ExampleFailController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.common.controller.example.ExamplePostController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def setUp(self):
		super(RouterTest, self).setUp()

		self.configuration['router']['nginx']['port_direct'] = self.configuration.get_free_port()
		self.configuration['router']['nginx']['port_80'] = self.configuration.get_free_port()
		self.configuration['router']['nginx']['port_443'] = self.configuration.get_free_port()
		self.configuration.update_flat()

		self.router = NginxRouter(self.configuration)
		self.router.startup(self.stop, self.stop)
		result = self.wait()

		config = self.router.get_configuration()

		# Save some parameters for other tests
		self.nginxport = self.configuration['router']['nginx']['port_direct']

		# For debugging... they are unlinked in tearDown()
		# but you can inspect them in the meantime.
		self.errorlog = os.path.join(config['log_path'], 'error.log')
		self.accesslog_stats = os.path.join(config['log_path'], 'access.log.paasmaker')
		self.accesslog_combined = os.path.join(config['log_path'], 'access.log')

	def tearDown(self):
		# Kill off the nginx instance.
		self.router.shutdown()

		super(RouterTest, self).tearDown()

	def get_redis_client(self):
		# CAUTION: The second callback is the error callback,
		# and this will break if it tries to call it. TODO: fix this.
		self.configuration.get_router_table_redis(self.stop, None)
		return self.wait()

	def get_stats_redis_client(self):
		# CAUTION: The second callback is the error callback,
		# and this will break if it tries to call it. TODO: fix this.
		self.configuration.get_stats_redis(self.stop, None)
		return self.wait()

	def test_simple_request(self):
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example" % self.nginxport,
			method="GET",
			headers={'Host': 'foo.com'})
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		# The response from nginx.
		#print response.body
		# The nginx error log - will contain lua debug info.
		#print open(self.errorlog, 'r').read()

		# Should be 500 - router redis does not yet exist.
		self.assertEquals(response.code, 500, "Response is not 500.")

		# Get the router redis. This fires up a redis instance.
		self.get_redis_client()

		# And try it again!
		client.fetch(request, self.stop)
		response = self.wait()

		#print response.body
		#print open(self.errorlog, 'r').read()
		#print open(self.accesslog_stats, 'r').read()
		#print open(self.accesslog_combined, 'r').read()

		# Should be 404 this time.
		self.assertEquals(response.code, 404, "Response is not 404 - got %d." % response.code)

		# Now insert a record for it.
		# Inserted records MUST be IP addresses.
		target = "127.0.0.1:%d#1#2#3" % self.get_http_port()
		redis = self.get_redis_client()
		redis.sadd('instances:foo.com', target, callback=self.stop)
		self.wait()
		redis.sadd('instances:*.foo.com', target, callback=self.stop)
		self.wait()

		# Fetch the set members.
		redis.smembers('instances:foo.com', callback=self.stop)
		members = self.wait()
		self.assertIn(target, members, "Target is not in set.")

		# And try it again!
		client.fetch(request, self.stop)
		response = self.wait()

		#print response.body
		#print open(self.errorlog, 'r').read()
		#print open(self.accesslog_stats, 'r').read()
		#print open(self.accesslog_combined, 'r').read()

		# Should be 200 this time.
		self.assertEquals(response.code, 200, "Response is not 200.")

		# Try with a port in the Host header.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example" % self.nginxport,
			method="GET",
			headers={'Host': 'foo.com:1000'})
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		# Should be 200.
		self.assertEquals(response.code, 200, "Response is not 200.")

		# Try to fetch the one level wildcard version.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example" % self.nginxport,
			method="GET",
			headers={'Host': 'www.foo.com'})
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		#print open(self.errorlog, 'r').read()
		#print open(self.accesslog_stats, 'r').read()

		self.assertEquals(response.code, 200, "Response is not 200.")

		# Now test reading the stats log.
		stats_reader = paasmaker.router.stats.StatsLogReader(self.configuration)
		stats_reader.read(self.stop, self.stop)
		result = self.wait()
		self.assertEquals(result, "Completed reading file.")

		# Read back the stats, and make sure they make some sense.
		stats_output = paasmaker.router.stats.ApplicationStats(self.configuration)
		stats_output.setup(self.stop, self.stop)
		# Wait for it to be ready.
		self.wait()

		# This is for uncaught requests.
		stats_output.total_for_uncaught(self.stop, self.stop)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(result['requests'], 2, "Wrong number of requests.")
		self.assertEquals(result['4xx'], 1, "Wrong number of requests.")
		self.assertEquals(result['5xx'], 1, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 500, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 1, "Wrong value returned.")
		# Time will be zero, because the backends were not invoked for these requests.
		self.assertTrue(result['time'] == 0, "Wrong value returned.")

		# Now check for the supplied version ID.
		stats_output.vtset_for_name('version_type', 1, self.stop)
		vtset = self.wait()
		#print json.dumps(vtset, indent=4, sort_keys=True)
		stats_output.total_for_list('vt', vtset, self.stop, self.stop)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(result['requests'], 3, "Wrong number of requests.")
		self.assertEquals(result['2xx'], 3, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 400, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 0, "Wrong value returned.")
		self.assertTrue(result['time'] > 0, "Wrong value returned.")

		# Check that we have the same stats for the node.
		stats_output.total_for_list('node', [2], self.stop, self.stop)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(result['requests'], 3, "Wrong number of requests.")
		self.assertEquals(result['2xx'], 3, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 400, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 0, "Wrong value returned.")
		self.assertTrue(result['time'] > 0, "Wrong value returned.")

		# Now try to fetch for a workspace ID. This won't exist,
		# because this unit test doesn't insert those records.
		stats_output.vtset_for_name('workspace', 1, self.stop)
		result = self.wait()
		self.assertEquals(len(result), 0, "Returned vtids for a workspace!")

		# Caution: the second callback here is the error callback.
		self.configuration.get_stats_redis(self.stop, None)
		stats_redis = self.wait()

		# Insert those records, and then try again.
		stats_redis.sadd('workspace:1', '1', callback=self.stop)
		self.wait()

		stats_output.vtset_for_name('workspace', 1, self.stop)
		vtset = self.wait()
		stats_output.total_for_list('vt', vtset, self.stop, self.stop)
		result = self.wait()

		# And the result should match the stats results for the
		# version type.
		self.assertEquals(result['requests'], 3, "Wrong number of requests.")
		self.assertEquals(result['2xx'], 3, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 400, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 0, "Wrong value returned.")
		self.assertTrue(result['time'] > 0, "Wrong value returned.")

		# This is to assist with debugging the history stats.
		#stats_redis = self.get_stats_redis_client()
		#stats_redis.keys('history_*', self.stop)
		#keys = self.wait()
		#print json.dumps(keys, indent=4, sort_keys=True)
		#for key in keys:
		#	stats_redis.hgetall(key, self.stop)
		#	hmap = self.wait()
		#	print json.dumps(hmap, indent=4, sort_keys=True)

		stats_output.vtset_for_name('version_type', 1, self.stop)
		vtset = self.wait()
		#print json.dumps(vtset, indent=4, sort_keys=True)
		stats_output.history('vt', vtset, 'requests', self.stop, self.stop, time.time() - 60)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(len(result), 1, "Wrong number of data points.")
		self.assertEquals(len(result[0]), 2, "Malformed response.")
		self.assertEquals(result[0][1], 3, "Wrong number of requests.")

		# Do the same thing for the node history.
		stats_output.history('node', [2], 'requests', self.stop, self.stop, time.time() - 60)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(len(result), 1, "Wrong number of data points.")
		self.assertEquals(len(result[0]), 2, "Malformed response.")
		self.assertEquals(result[0][1], 3, "Wrong number of requests.")
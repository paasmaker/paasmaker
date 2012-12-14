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
	NGINX_CONFIG = """
worker_processes 1;
error_log %(log_path)s/error.log %(log_level)s;
pid %(pid_path)s/nginx.pid;

events {
	worker_connections  256;
}

http {
	log_format paasmaker '{"key":"$logkey","bytes":$bytes_sent,'
		'"code":$status,"upstream_response_time":"$upstream_response_time",'
		'"time":"$time_iso8601","timemsec":$msec,"nginx_response_time":$request_time}';

	access_log %(log_path)s/access.log.paasmaker paasmaker;
	access_log %(log_path)s/access.log combined;

	%(temp_paths)s

	server {
		listen       %(listen_port)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
			set $logkey "null";
			rewrite_by_lua_file %(router_root)s/rewrite.lua;

			proxy_set_header            Host $host;
			proxy_buffering             off;
			proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header            X-Forwarded-Port 80;
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

	@staticmethod
	def get_nginx_config(configuration, managed_params=None):
		parameters = {}

		if managed_params:
			parameters['temp_dir'] = managed_params['temp_path']
			parameters['listen_port'] = managed_params['port']
			parameters['log_path'] = managed_params['log_path']
			parameters['temp_paths'] = NginxRouter.TEMP_PATHS % {'temp_dir': managed_params['temp_path']}
			parameters['pid_path'] = managed_params['pid_path']
			parameters['log_level'] = managed_params['log_level']
		else:
			parameters['listen_port'] = 80
			# TODO: This is Linux specific.
			parameters['log_path'] = '/var/log/nginx'
			parameters['pid_path'] = '/var/run/nginx.pid'
			parameters['temp_paths'] = ""
			parameters['log_level'] = 'info'

		parameters['redis_host'] = configuration.get_flat('redis.table.host')
		parameters['redis_port'] = configuration.get_flat('redis.table.port')

		# This is where the LUA files are stored.
		parameters['router_root'] = os.path.normpath(os.path.dirname(__file__))

		configuration = NginxRouter.NGINX_CONFIG % parameters

		parameters['configuration'] = configuration

		return parameters

class RouterTest(paasmaker.common.controller.base.BaseControllerTest):
	config_modules = ['pacemaker', 'router']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = paasmaker.common.controller.example.ExampleController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.common.controller.example.ExampleFailController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.common.controller.example.ExamplePostController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.common.controller.example.ExampleWebsocketHandler.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def setUp(self):
		super(RouterTest, self).setUp()

		managed_params = {}
		managed_params['port'] = self.configuration.get_free_port()
		managed_params['log_path'] = tempfile.mkdtemp()
		managed_params['temp_path'] = self.configuration.get_scratch_path_exists('nginx')
		managed_params['pid_path'] = managed_params['temp_path']
		managed_params['log_level'] = 'debug'

		self.nginx = NginxRouter.get_nginx_config(self.configuration, managed_params=managed_params)

		# Fire up an nginx instance.
		self.nginxconfig = tempfile.mkstemp()[1]
		self.nginxpidfile = os.path.join(self.nginx['pid_path'], 'nginx.pid')
		self.nginxport = self.nginx['listen_port']

		# For debugging... they are unlinked in tearDown()
		# but you can inspect them in the meantime.
		self.errorlog = os.path.join(self.nginx['log_path'], 'error.log')
		self.accesslog_stats = os.path.join(self.nginx['log_path'], 'access.log.paasmaker')
		self.accesslog_combined = os.path.join(self.nginx['log_path'], 'access.log')

		# Hack the configuration to insert the access log into it.
		self.configuration['router']['stats_log'] = self.accesslog_stats
		self.configuration.update_flat()

		open(self.nginxconfig, 'w').write(self.nginx['configuration'])

		# Kick off the instance. It will fork in the background once it's
		# successfully started.
		# check_call throws an exception if it failed to start.
		subprocess.check_call([self.configuration.get_flat('nginx_binary'), '-c', self.nginxconfig], stderr=subprocess.PIPE)

	def tearDown(self):
		# Kill off the nginx instance.
		pid = int(open(self.nginxpidfile, 'r').read())
		os.kill(pid, signal.SIGTERM)

		# Remove all the temp files.
		os.unlink(self.nginxconfig)
		os.unlink(self.errorlog)
		os.unlink(self.accesslog_stats)
		os.unlink(self.accesslog_combined)

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
		self.assertEquals(response.code, 404, "Response is not 404.")

		# Now insert a record for it.
		# Inserted records MUST be IP addresses.
		target = "127.0.0.1:%d" % self.get_http_port()
		redis = self.get_redis_client()
		redis.sadd('instances_foo.com', target, callback=self.stop)
		self.wait()
		logkey = 1
		redis.set('logkey_foo.com', logkey, callback=self.stop)
		self.wait()
		target = "127.0.0.1:%d" % self.get_http_port()
		redis.sadd('instances_*.foo.com', target, callback=self.stop)
		self.wait()
		logkey = 1
		redis.set('logkey_*.foo.com', logkey, callback=self.stop)
		self.wait()

		# Fetch the set members.
		redis.smembers('instances_foo.com', callback=self.stop)
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
		stats_output.total_for_list(vtset, self.stop, self.stop)
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
		stats_redis.sadd('workspace_1_vtids', '1', callback=self.stop)
		self.wait()

		stats_output.vtset_for_name('workspace', 1, self.stop)
		vtset = self.wait()
		stats_output.total_for_list(vtset, self.stop, self.stop)
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
		stats_output.history_for_list(vtset, 'requests', self.stop, self.stop, time.time() - 60)
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(len(result), 1, "Wrong number of data points.")
		self.assertEquals(len(result[0]), 2, "Malformed response.")
		self.assertEquals(result[0][1], 3, "Wrong number of requests.")
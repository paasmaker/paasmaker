import unittest
import os
import subprocess
import tempfile
import shutil
import signal
import json

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
	def get_nginx_config(configuration, unit_test=False):
		parameters = {}

		parameters['temp_dir'] = configuration.get_scratch_path_exists('nginx')

		if unit_test:
			parameters['listen_port'] = configuration.get_free_port()
			parameters['log_path'] = tempfile.mkdtemp()
			parameters['temp_paths'] = NginxRouter.TEMP_PATHS % parameters
			parameters['pid_path'] = parameters['temp_dir']
			parameters['log_level'] = 'debug'
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

		self.nginx = NginxRouter.get_nginx_config(self.configuration, unit_test=True)

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
		stats_output = paasmaker.router.stats.ApplicationStats(self.configuration, self.stop, self.stop)

		# This is for uncaught requests.
		stats_output.for_version_type('null')
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
		stats_output.for_version_type('1')
		result = self.wait()
		#print json.dumps(result, indent=4, sort_keys=True)

		self.assertEquals(result['requests'], 2, "Wrong number of requests.")
		self.assertEquals(result['2xx'], 2, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 400, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 0, "Wrong value returned.")
		self.assertTrue(result['time'] > 0, "Wrong value returned.")

		# Now try to fetch for a workspace ID. This won't exist,
		# because this unit test doesn't insert those records.
		stats_output.for_workspace(1)
		result = self.wait()
		self.assertIn("No such", result, "Wrong error message.")

		# Caution: the second callback here is the error callback.
		self.configuration.get_stats_redis(self.stop, None)
		stats_redis = self.wait()

		# Insert those records, and then try again.
		stats_redis.sadd('workspace_1_vtids', '1', callback=self.stop)
		self.wait()

		stats_output.for_workspace(1)
		result = self.wait()

		# And the result should match the stats results for the
		# version type.
		self.assertEquals(result['requests'], 2, "Wrong number of requests.")
		self.assertEquals(result['2xx'], 2, "Wrong number of requests.")
		self.assertTrue(result['bytes'] > 400, "Wrong value returned.")
		self.assertTrue(result['nginxtime'] > 0, "Wrong value returned.")
		self.assertTrue(result['time'] > 0, "Wrong value returned.")
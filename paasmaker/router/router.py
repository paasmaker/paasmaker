import unittest
import os
import subprocess
import tempfile
import shutil
import signal

import paasmaker
import tornado.testing

NGINX_CONFIG = """
worker_processes  1;
error_log  %(error_log)s debug;
pid %(temp_dir)s/nginx.pid;

events {
	worker_connections  256;
}

http {
	log_format paasmaker '{"key":$logkey,"bytes":$bytes_sent,'
		'"code":$status,"upstream_response_time":"$upstream_response_time",'
		'"time":$msec,"nginx_response_time":$request_time}';

	access_log %(access_log_stats)s paasmaker;
	access_log %(access_log_combined)s combined;

	client_body_temp_path %(temp_dir)s/;
	proxy_temp_path %(temp_dir)s/;
	fastcgi_temp_path %(temp_dir)s/;
	uwsgi_temp_path %(temp_dir)s/;
	scgi_temp_path %(temp_dir)s/;

	server {
		listen       %(test_port)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
			set $logkey "null";
			rewrite_by_lua_file %(router_root)s/rewrite.lua;
			proxy_set_header Host $host;
			proxy_buffering             off;
			proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header            X-Forwarded-Port 80;
			proxy_redirect              off;
			proxy_connect_timeout       10;
			proxy_send_timeout          60;
			proxy_read_timeout          60;
			proxy_pass http://$upstream;
		}
	}
}
"""

class RouterTest(paasmaker.common.controller.base.BaseControllerTest):
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

		# Fire up an nginx instance.
		self.nginxconfig = tempfile.mkstemp()[1]
		self.nginxtempdir = tempfile.mkdtemp()
		self.nginxpidfile = os.path.join(self.nginxtempdir, 'nginx.pid')
		self.nginxport = self.configuration.get_free_port()

		# For debugging... they are unlinked in tearDown()
		# but you can inspect them in the meantime.
		self.errorlog = tempfile.mkstemp()[1]
		self.accesslog_stats = tempfile.mkstemp()[1]
		self.accesslog_combined = tempfile.mkstemp()[1]

		nginxparams = {}
		nginxparams['temp_dir'] = self.nginxtempdir
		nginxparams['router_root'] = os.path.normpath(os.path.dirname(__file__))
		nginxparams['test_port'] = self.nginxport
		nginxparams['error_log'] = self.errorlog
		nginxparams['access_log_stats'] = self.accesslog_stats
		nginxparams['access_log_combined'] = self.accesslog_combined

		# NOTE: The host might be 0.0.0.0, but this will still work
		# on the managing host.
		nginxparams['redis_host'] = self.configuration.get_flat('redis.table.host')
		nginxparams['redis_port'] = self.configuration.get_flat('redis.table.port')

		config = NGINX_CONFIG % nginxparams
		open(self.nginxconfig, 'w').write(config)

		# Kick off the instance. It will fork in the background once it's
		# successfully started.
		# check_call throws an exception if it failed to start.
		subprocess.check_call([self.configuration.get_flat('nginx_binary'), '-c', self.nginxconfig], stderr=subprocess.PIPE)

	def tearDown(self):
		super(RouterTest, self).tearDown()

		# Kill off the nginx instance.
		pid = int(open(self.nginxpidfile, 'r').read())
		os.kill(pid, signal.SIGTERM)

		# Remove all the temp files.
		shutil.rmtree(self.nginxtempdir)
		os.unlink(self.nginxconfig)
		os.unlink(self.errorlog)
		os.unlink(self.accesslog_stats)
		os.unlink(self.accesslog_combined)

	def get_redis_client(self):
		# CAUTION: The second callback is the error callback,
		# and this will break if it tries to call it.
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

		self.assertEquals(response.code, 200, "Response is not 200.")
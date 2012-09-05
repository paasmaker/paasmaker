#!/usr/bin/env python

import unittest
import os
import subprocess
import tempfile
import shutil
import signal

import paasmaker
import tornado.testing

# TODO: This is specific to the setup.
NGINX_BINARY_PATH = "/usr/local/openresty/nginx/sbin/nginx"

NGINX_CONFIG = """
worker_processes  1;
error_log  %(error_log)s debug;
pid %(temp_dir)s/nginx.pid;

events {
	worker_connections  256;
}

http {
	access_log %(access_log)s;

	client_body_temp_path %(temp_dir)s/;
	proxy_temp_path %(temp_dir)s/;
	fastcgi_temp_path %(temp_dir)s/;
	uwsgi_temp_path %(temp_dir)s/;
	scgi_temp_path %(temp_dir)s/;

	access_log /dev/stdout;

	server {
		listen       %(test_port)d;
		server_name  localhost;

		location / {
			set $redis_host %(redis_host)s;
			set $redis_port %(redis_port)d;
			set $upstream "";
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

class RouterTest(paasmaker.controller.base.BaseControllerTest):
	def get_app(self):
		routes = paasmaker.controller.example.ExampleController.get_routes({'configuration': self.configuration})
		routes.extend(paasmaker.controller.example.ExampleFailController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.controller.example.ExamplePostController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.controller.example.ExampleWebsocketHandler.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_torando_configuration())
		return application

	def setUp(self):
		super(RouterTest, self).setUp()

		self.redis = self.configuration.get_redis(self)
		self.redisconfig = self.configuration.get_redis_configuration()

		# Fire up an nginx instance.
		self.nginxconfig = tempfile.mkstemp()[1]
		self.nginxtempdir = tempfile.mkdtemp()
		self.nginxpidfile = os.path.join(self.nginxtempdir, 'nginx.pid')
		self.nginxport = tornado.testing.get_unused_port()

		# For debugging... they are unlinked in tearDown()
		# but you can inspect them in the meantime.
		self.errorlog = tempfile.mkstemp()[1]
		self.accesslog = tempfile.mkstemp()[1]

		nginxparams = {}
		nginxparams['temp_dir'] = self.nginxtempdir
		nginxparams['router_root'] = os.path.normpath(os.path.dirname(__file__) + '/../../router')
		nginxparams['test_port'] = self.nginxport
		nginxparams['error_log'] = self.errorlog
		nginxparams['access_log'] = self.accesslog
		nginxparams['redis_host'] = self.redisconfig['host']
		nginxparams['redis_port'] = self.redisconfig['port']

		config = NGINX_CONFIG % nginxparams
		open(self.nginxconfig, 'w').write(config)

		# Kick off the instance. It will fork in the background once it's
		# successfully started.
		# check_call throws an exception if it failed to start.
		subprocess.check_call([NGINX_BINARY_PATH, '-c', self.nginxconfig])

	def tearDown(self):
		super(RouterTest, self).tearDown()

		# Kill off the nginx instance.
		pid = int(open(self.nginxpidfile, 'r').read())
		os.kill(pid, signal.SIGTERM)

		# Remove all the temp files.
		shutil.rmtree(self.nginxtempdir)
		os.unlink(self.nginxconfig)
		os.unlink(self.errorlog)
		os.unlink(self.accesslog)

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

		# Should be 'not found'.
		self.assertEquals(response.code, 404, "Response is not 404.")

		# Now insert a record for it.
		# Inserted records MUST be IP addresses.
		target = "127.0.0.1:%d" % self.get_http_port()
		self.redis.sadd('foo.com', target, callback=self.stop)
		self.wait()

		# Fetch the set members.
		self.redis.smembers('foo.com', callback=self.stop)
		members = self.wait()
		self.assertIn(target, members, "Target is not in set.")

		# And try it again!
		client.fetch(request, self.stop)
		response = self.wait()

		#print response.body
		#print open(self.errorlog, 'r').read()

		# Should be 200 this time.
		self.assertEquals(response.code, 200, "Response is not 200.")

if __name__ == '__main__':
	unittest.main()

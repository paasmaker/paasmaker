
import os
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest

import paasmaker
from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado.testing
import tornadoredis

class NginxDaemonError(ManagedDaemonError):
	def __init__(self, cmd, returncode, message, output):
		self.cmd = cmd
		self.returncode = returncode
		self.message = message
		self.output = output

	def __str__(self):
		return "Couldn't start nginx: returned status %d with message %s and output %s; command was %s" % (self.returncode, self.message, self.output, self.cmd)

class NginxDaemon(ManagedDaemon):
	"""
	Start a managed instance of the NGINX web server.

	It is configured as appropriate for the Paasmaker
	configuration it is started with, to be a router.
	It is not a general purpose NGINX server.

	The main design goal here is to allow Paasmaker to
	start it's own managed routing servers.
	"""

	def configure(self, working_dir, port_to_monitor, config_file_string):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg int port_direct: The "direct" port to listen on.
		:arg int port_80: The "port 80" port to listen on.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port_to_monitor
		self.parameters['config_file_string'] = config_file_string

		self.save_parameters()

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'nginx.pid')

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])

		fp = open(configfile, 'w')
		fp.write(self.parameters['config_file_string'])
		fp.close()

		# Fire up the server.
		logging.info("Starting up nginx server on port %d." % self.parameters['port'])

		try:
			foo = subprocess.check_call(
				[
					self.configuration.get_flat('nginx_binary'),
					'-c',
					self.get_configuration_path(self.parameters['working_dir'])
				],
				stderr=subprocess.PIPE
			)
		except subprocess.CalledProcessError, ex:
			raise NginxDaemonError(ex.cmd, ex.returncode, ex.message, ex.output)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def is_running(self, keyword=None):
		return super(NginxDaemon, self).is_running('nginx')

	def destroy(self):
		"""
		Destroy this instance of nginx, removing all assigned data.
		"""
		self.stop()
		shutil.rmtree(self.parameters['working_dir'])

class NginxDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(NginxDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

		self.test_config_file = """
error_log %(working_dir)s/error.log info;
pid %(working_dir)s/nginx.pid;
events {
    worker_connections  1024;
}

http {
	access_log %(working_dir)s/access.log combined;

	server {
		listen       %(port)d;
		server_name  localhost;

		location / {
			root %(working_dir)s;
		}
	}
}
"""
	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(NginxDaemonTest, self).tearDown()

	def test_basic(self):
		self.server = NginxDaemon(self.configuration)

		parameters = {}
		parameters['port'] = self.configuration.get_free_port()
		parameters['working_dir'] = self.configuration.get_scratch_path_exists('nginx')

		test_string = "This is a test of the NginxDaemon class"

		fp = open(os.path.join(parameters['working_dir'], "index.html"), 'w')
		fp.write(test_string)
		fp.close()

		self.server.configure(
			parameters['working_dir'],
			parameters['port'],
			self.test_config_file % parameters
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start nginx server.")

		# Connect to it. It should give us a 500 server error.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/foo' % parameters['port'])
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 404, "Got unexpected response code %d" % response.code)
		self.assertIn("404 Not Found", response.body, "Response body didn't contain 404 error text")

		# Connect to it. It should give us a 500 server error.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/' % parameters['port'])
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 200, "Got unexpected response code %d" % response.code)
		self.assertEquals(test_string, response.body, "Index page didn't contain the contents we expected: %s" % response.body)

		self.server.stop()

		# Give it a little time to stop.
		time.sleep(0.1)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start nginx server.")

		self.assertTrue(self.server.is_running())
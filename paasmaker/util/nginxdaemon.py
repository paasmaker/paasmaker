#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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

	def configure(self, working_dir, port_to_monitor, config_file_string, callback, error_callback):
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

		callback("Configured.")

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

		def process_forked(code):
			if code == 0:
				# Wait for the port to come into use.
				logging.info("NGINX started, waiting for listening state.")
				self._wait_until_port_inuse(
					self.parameters['port'],
					callback,
					error_callback
				)
			else:
				error_message = "Unable to start NGINX - exited with error code %d." % code
				error_message += "Output:\n" + self._fetch_output()
				logging.error(error_message)
				error_callback(error_message)

		# Fire up the server.
		logging.info("Starting up nginx server on port %d." % self.parameters['port'])
		try:
			paasmaker.util.popen.Popen(
				[
					self.configuration.get_flat('nginx_binary'),
					'-c',
					self.get_configuration_path(self.parameters['working_dir'])
				],
				redirect_stderr=True,
				on_stdout=self._fetchable_output,
				on_exit=process_forked,
				io_loop=self.configuration.io_loop
			)
		except OSError, ex:
			logging.error(ex)
			error_callback(str(ex), exception=ex)

	def is_running(self, keyword=None):
		return super(NginxDaemon, self).is_running('nginx')

	def destroy(self, callback, error_callback):
		"""
		Destroy this instance of nginx, removing all assigned data.
		"""
		def stopped(message):
			# Delete all the files.
			shutil.rmtree(self.parameters['working_dir'])
			callback(message)

		# Hard shutdown - we're about to delete the data anyway.
		self.stop(stopped, error_callback, signal.SIGKILL)

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
			self.server.destroy(self.stop, self.stop)
			self.wait()
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
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
			self.test_config_file % parameters,
			self.stop,
			self.stop
		)
		self.wait()
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

		self.server.stop(self.stop, self.stop)
		self.wait()

		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start nginx server.")

		self.assertTrue(self.server.is_running())
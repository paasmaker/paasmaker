
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

class ManagedNginxError(ManagedDaemonError):
	pass

class ManagedNginx(ManagedDaemon):
	"""
	Start a managed instance of the NGINX web server.

	It is configured as appropriate for the Paasmaker
	configuration it is started with, to be a router.
	It is not a general purpose NGINX server.

	The main design goal here is to allow Paasmaker to
	start it's own managed routing servers.
	"""

	def configure(self, working_dir, port):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg int port: The port to listen on.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)
		# And create a directory for temp files.
		temp_file_dir = os.path.join(working_dir, 'temp')
		if not os.path.exists(temp_file_dir):
			os.makedirs(temp_file_dir)

		self.save_parameters()

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'nginx.pid')

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		parameters = {}
		parameters['port'] = self.parameters['port']
		parameters['temp_path'] = os.path.join(self.parameters['working_dir'], 'temp')
		parameters['pid_path'] = self.parameters['working_dir']
		parameters['log_level'] = 'info'
		parameters['log_path'] = self.parameters['working_dir']

		configuration = paasmaker.router.router.NginxRouter.get_nginx_config(
			self.configuration, managed_params=parameters
		)

		fp = open(configfile, 'w')
		fp.write(configuration['configuration'])
		fp.close()

		# Fire up the server.
		logging.info("Starting up nginx server on port %d." % self.parameters['port'])
		subprocess.check_call(
			[
				self.configuration.get_flat('nginx_binary'),
				'-c',
				self.get_configuration_path(self.parameters['working_dir'])
			],
			stderr=subprocess.PIPE
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def is_running(self, keyword=None):
		return super(ManagedNginx, self).is_running('nginx')

	def destroy(self):
		"""
		Destroy this instance of nginx, removing all assigned data.
		"""
		self.stop()
		shutil.rmtree(self.parameters['working_dir'])

class ManagedNginxTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ManagedNginxTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(ManagedNginxTest, self).tearDown()

	def test_basic(self):
		self.server = ManagedNginx(self.configuration)
		port = self.configuration.get_free_port()
		self.server.configure(
			self.configuration.get_scratch_path_exists('nginx'),
			port
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start nginx server.")

		# Connect to it. It should give us a 500 server error.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/foo' % port)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 500, "Wrong response code.")
		self.assertTrue(len(response.body) > 0, "Didn't return a body.")

		self.server.stop()

		# Give it a little time to stop.
		time.sleep(0.1)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start nginx server.")

		self.assertTrue(self.server.is_running())
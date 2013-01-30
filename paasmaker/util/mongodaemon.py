
import os
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest
from distutils.spawn import find_executable

import paasmaker
from ..common.testhelpers import TestHelpers
from ..util.port import FreePortFinder
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado
from pymongo import MongoClient

class MongoDaemonError(ManagedDaemonError):
	pass

class MongoDaemon(ManagedDaemon):
	"""
	Start up a managed mongoDB daemon.

	Note: this class is incomplete; e.g. there is currently no support for
	authentication. Journalling is also disabled, to avoid a 45-60 second
	startup time, but this ought to be configurable.
	"""

	MONGO_SERVER_CONFIG = """
fork = true
bind_ip = %(host)s
port = %(port)d
quiet = true
dbpath = %(working_dir)s
logpath = %(working_dir)s/mongod.log
pidfilepath = %(working_dir)s/mongodb.pid
logappend = true
nojournal = true
smallfiles = true
"""

	def configure(self, working_dir, binary_path, port, bind_host, password=None):
		"""
		Configure this mongoDB instance.

		:arg str working_dir: The working directory to store files.
		:arg int port: The TCP port to listen on.
		:arg str bind_host: The IP address to bind to.
		:arg str|None password: If supplied, clients will require
			this password to connect to the daemon.
		"""
		# TODO: Allow a memory limit.
		# TODO: Allow custom configuration entries.
		self.parameters['working_dir'] = working_dir
		self.parameters['binary_path'] = binary_path
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		
		# TODO: allow this to be configured by service users
		# journal_str = "journal = true" if enabled else "nojournal = true"

		# TODO: support authentication
		# self.parameters['password'] = password

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		self.save_parameters()

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'mongodb.pid')

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		mongoconfig = self.MONGO_SERVER_CONFIG % self.parameters
		fp = open(configfile, 'w')
		fp.write(mongoconfig)
		fp.close()

		# Fire up the server.
		logging.info("Starting up mongoDB server on port %d." % self.parameters['port'])
		subprocess.check_call(
			[
				self.parameters['binary_path'], '-f',
				self.get_configuration_path(self.parameters['working_dir'])
			]
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def get_client(self):
		"""
		Get a mongoDB client object for this instance.

		CAUTION: This should only be used for unit tests. It
		returns a persistent connection that could cause some
		weird behaviour with production use.
		"""
		if self.client:
			return self.client

		# Create a client for it.
		
		self.client = MongoClient(
			self.parameters['host'],
			self.parameters['port']
		)

		return self.client

	def is_running(self, keyword=None):
		return super(MongoDaemon, self).is_running('mongod')

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the mongoDB server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		super(MongoDaemon, self).stop(sig)

	def destroy(self):
		"""
		Destroy this instance of mongoDB, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class MongoDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(MongoDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)
		self.mongodb_binary = find_executable("mongod")

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(MongoDaemonTest, self).tearDown()

	def callback(self, channel, method, header, body):
		# Print out the message.
		#print body
		# Signal that we got it.
		self.stop()

	def test_configure_and_run(self):
		# TODO: the testsuite will eventually either load paasmaker.yml, and/or
		# use locally-installed versions of daemons from the install script.
		self.assertIsNotNone(self.mongodb_binary, "mongoDB server is not in your PATH; this test cannot run")

		working_dir = self.configuration.get_scratch_path_exists('mongodb')
		port = self.configuration.get_free_port()
		host = '127.0.0.1'

		self.server = MongoDaemon(self.configuration)
		self.server.configure(working_dir, self.mongodb_binary, port, host)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start mongoDB server.")

		self.assertTrue(self.server.is_running(), "mongoDB daemon class doesn't report that it is running")

		fp = FreePortFinder()
		self.assertTrue(fp.in_use(port), "mongoDB daemon's port does not appear to be in use")

		client = MongoClient(host, port)
		info = client.server_info()
		self.assertEquals(info['ok'], 1.0, "mongoDB server_info() does not report that it's OK!")

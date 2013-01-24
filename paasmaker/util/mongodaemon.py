
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

from pymongo import MongoClient

class MongoDaemonError(ManagedDaemonError):
	pass

class MongoDaemon(ManagedDaemon):
	"""
	Start up a managed mongoDB daemon.

	Currently, it chooses some persistence options that match
	the default Ubuntu/Debian configuration. In future it will
	offer other canned persistence options to better suit
	what the server is being used for.
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
journal = true
"""

	def configure(self, working_dir, port, bind_host, password=None):
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
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		self.parameters['password'] = password

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
				self.configuration.get_flat('mongodb_binary'), '-f',
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
			host=self.parameters['host'],
			port=self.parameters['port']
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

#class MongoDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
#	def setUp(self):
#		super(MongoDaemonTest, self).setUp()
#		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)
#
#	def tearDown(self):
#		if hasattr(self, 'server'):
#			self.server.destroy()
#		self.configuration.cleanup()
#		super(MongoDaemonTest, self).tearDown()
#
#	def callback(self, channel, method, header, body):
#		# Print out the message.
#		#print body
#		# Signal that we got it.
#		self.stop()
#
#	def test_basic(self):
#		self.server = MongoDaemon(self.configuration)
#		self.server.configure(
#			self.configuration.get_scratch_path_exists('mongodb'),
#			self.configuration.get_free_port(),
#			'127.0.0.1'
#		)
#		self.server.start(self.stop, self.stop)
#		result = self.wait()
#
#		self.assertIn("In appropriate state", result, "Failed to start mongoDB server.")
#
#		client = self.server.get_client()
#
#		client.set('test', 'foo', callback=self.stop)
#		self.wait()
#
#		client.get('test', callback=self.stop)
#		result = self.wait()
#
#		self.assertEquals('foo', result, "Result was not as expected.")
#
		# TODO: Test stopping and resuming the service.
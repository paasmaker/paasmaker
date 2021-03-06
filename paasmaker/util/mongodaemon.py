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

	def configure(self, working_dir, binary_path, port, bind_host, callback, error_callback, password=None):
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

		callback("Configured successfully.")

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

		def process_forked(code):
			if code == 0:
				# Wait for the port to come into use.
				logging.info("mongoDB started, waiting for listening state.")
				self._wait_until_port_inuse(
					self.parameters['port'],
					callback,
					error_callback
				)
			else:
				error_message = "Unable to start mongoDB - exited with error code %d." % code
				error_message += "Output:\n" + self._fetch_output()
				logging.error(error_message)
				error_callback(error_message)

		# Fire up the server.
		logging.info("Starting up mongoDB server on port %d." % self.parameters['port'])
		try:
			paasmaker.util.popen.Popen(
				[
					self.parameters['binary_path'], '--config',
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

	def stop(self, callback, error_callback, sig=signal.SIGTERM):
		"""
		Stop this instance of the mongoDB server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.disconnect()
			self.client = None

		super(MongoDaemon, self).stop(callback, error_callback, sig)

	def destroy(self, callback, error_callback):
		"""
		Destroy this instance of mongoDB, removing all assigned data.
		"""
		def stopped(message):
			# Delete all the files.
			shutil.rmtree(self.parameters['working_dir'])
			callback(message)

		# Hard shutdown - we're about to delete the data anyway.
		self.stop(stopped, error_callback, signal.SIGKILL)

class MongoDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(MongoDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)
		self.mongodb_binary = find_executable("mongod")

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy(self.stop, self.stop)
			self.wait()
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(MongoDaemonTest, self).tearDown()

	def callback(self, channel, method, header, body):
		# Print out the message.
		#print body
		# Signal that we got it.
		self.stop()

	def test_configure_and_run(self):
		if not self.mongodb_binary:
			self.skipTest("mongodb is not installed; so we can't test this service.")
			return

		working_dir = self.configuration.get_scratch_path_exists('mongodb')
		port = self.configuration.get_free_port()
		host = '127.0.0.1'

		self.server = MongoDaemon(self.configuration)
		self.server.configure(working_dir, self.mongodb_binary, port, host, self.stop, self.stop)
		result = self.wait()
		self.assertIn("success", result, "Not configured.")
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start mongoDB server.")

		self.assertTrue(self.server.is_running(), "mongoDB daemon class doesn't report that it is running")

		fp = FreePortFinder()
		self.assertTrue(fp.in_use(port), "mongoDB daemon's port does not appear to be in use")

		client = MongoClient(host, port)
		info = client.server_info()
		self.assertEquals(info['ok'], 1.0, "mongoDB server_info() does not report that it's OK!")

		# Stop it and restart it.
		self.server.stop(self.stop, self.stop)
		result = self.wait()

		self.assertIn("finished", result, "Wrong return message.")

		self.server.start(self.stop, self.stop)

		result = self.wait()
		self.assertIn("In appropriate state", result, "Failed to start mongoDB server.")
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid
import subprocess
import unittest
import tornado.testing
import paasmaker
import tempfile
import shutil
import os
import logging
import time
import signal
from paasmaker.thirdparty.pika import TornadoConnection
import pika

from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

class ManagedRabbitMQError(ManagedDaemonError):
	pass

# was in common/configuration/configuration.py
# rabbitmq_binary = colander.SchemaNode(colander.String(),
# 	title="RabbitMQ server binary",
# 	description="The full path to the RabbitMQ server binary.",
# 	default="/usr/lib/rabbitmq/bin/rabbitmq-server",
# 	missing="/usr/lib/rabbitmq/bin/rabbitmq-server")

class ManagedRabbitMQ(ManagedDaemon):
	"""
	.. warning::
		This class is not in a working state.

	Start a managed instance of a RabbitMQ server.

	No passwords or authentication details are set up on the new node.

	If you plan to use multiple nodes, give each one a different
	``nodepurpose`` argument when calling ``configure()``. This
	prevents the RabbitMQ's from conflicting with each other.

	Please note that it can take 5-7 seconds to start the daemon.

	This was originally designed for unit tests, but later in
	development the code was rearranged to not require RabbitMQ,
	and as such this was no longer used.
	"""

	RABBITMQ_SERVER_CONFIG = """
[
    {rabbit, [{tcp_listeners, [%(RABBITMQ_PORT)s]}]}
].
"""

	def configure(self, working_dir, port, bind_host, nodepurpose=None):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg int port: The port to listen on.
		:arg str bind_host: The address to bind to.
		:arg str|None nodepurpose: An optional string to append
			to the node name to make it unique.
		"""
		# TODO: Allow authentication.
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		if nodepurpose:
			self.parameters['nodename'] = '%s-paasmaker@localhost' % nodepurpose
		else:
			self.parameters['nodename'] = 'paasmaker@localhost'
		self.parameters['pidfile'] = os.path.join(working_dir, self.parameters['nodename'] + '.pid')
		self.parameters['logfile'] = os.path.join(working_dir, 'rabbitmq.log')

		environment = {}
		environment['HOME'] = working_dir
		environment['RABBITMQ_BASE'] = working_dir
		environment['RABBITMQ_HOME'] = working_dir
		environment['RABBITMQ_MNESIA_BASE'] = working_dir
		environment['RABBITMQ_LOG_BASE'] = working_dir
		environment['RABBITMQ_NODENAME'] = self.parameters['nodename']
		environment['RABBITMQ_PORT'] = str(self.parameters['port'])
		environment['RABBITMQ_CONFIG_FILE'] = self.get_configuration_path(working_dir)

		self.parameters['environment'] = environment

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		self.save_parameters()

	def get_pid_path(self):
		return self.parameters['pidfile']

	def is_running(self, keyword=None):
		return super(ManagedRabbitMQ, self).is_running('rabbitmq')

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		rabbitconfig = self.RABBITMQ_SERVER_CONFIG % self.parameters['environment']
		fp = open(configfile  + '.config', 'w')
		fp.write(rabbitconfig)
		fp.close()

		logfp = open(self.parameters['logfile'], 'a')

		# Fire up the server.
		logging.info("Starting up RabbitMQ server on port %d (can take up to 10 seconds)." % self.parameters['port'])
		subprocess.Popen(
			[self.configuration.get_flat('rabbitmq_binary')],
			env=self.parameters['environment'],
			stdout=logfp,
			stderr=logfp
		)

		def error(message):
			log_file = open(self.parameters['logfile'], 'r').read()
			error_callback(log_file)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error
		)

	def get_client(self, callback=None):
		credentials = pika.PlainCredentials('guest', 'guest')
		# This will connect immediately.
		parameters = pika.ConnectionParameters(host=self.parameters['host'],
			port=self.parameters['port'],
			virtual_host='/',
			credentials=credentials)
		self.client = TornadoConnection(parameters, on_open_callback=callback, io_loop=self.configuration.io_loop)
		# TODO: This supresses some warnings during unit tests, but maybe is not good for production.
		self.client.set_backpressure_multiplier(1000)
		return self.client

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the rabbitmq server, allowing for it to be restarted later.
		"""
		if self.client:
			self.client.close()

		super(ManagedRabbitMQ, self).stop(sig)

	def destroy(self):
		"""
		Destroy this instance of rabbitmq, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class ManagedRabbitMQTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ManagedRabbitMQTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(ManagedRabbitMQTest, self).tearDown()

	def callback(self, channel, method, header, body):
		# Print out the message.
		#print body
		# Signal that we got it.
		self.stop()

	def test_basic(self):
		self.server = ManagedRabbitMQ(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('rabbitmq'),
			self.configuration.get_free_port(),
			'127.0.0.1'
		)
		self.server.start(self.stop, self.stop)
		result = self.wait(timeout=10)

		# Result contains the log file if it failed.
		#print result
		self.assertIn("In appropriate state", result, "Failed to start RabbitMQ server.")

		# Set up the client.
		client = self.server.get_client(callback=self.stop)
		self.wait()

		# Set up a basic channel.
		client.channel(self.stop)
		ch = self.wait()
		ch.queue_declare(queue='hello', callback=self.stop)
		self.wait()
		ch.basic_consume(consumer_callback=self.callback, queue='hello', no_ack=True)

		# Wait for that to be set up.
		self.short_wait_hack()

		# Publish a message.
		ch.basic_publish(body='Message from the Rabbits.', exchange='', routing_key='hello')

		# Wait until the message is received.
		self.wait()

		# Finish up.
		client.close()

		# TODO: Test stopping and resuming the service.
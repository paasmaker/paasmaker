
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

# https://github.com/pika/pika/blob/master/examples/demo_tornado.py

class TemporaryRabbitMQ:
	# TODO: Ubuntu specific, most likely!
	server_binary_path = "/usr/lib/rabbitmq/bin/rabbitmq-server"
	server_config = """
[
    {rabbit, [{tcp_listeners, [%(RABBITMQ_PORT)s]}]}
].
"""

	def __init__(self, configuration):
		self.started = False
		self.configuration = configuration
		self.client = None

	def start(self):
		# Choose some configuration values.
		self.dir = tempfile.mkdtemp()
		self.nodename = "paasmaker@localhost"
		self.pidfile = os.path.join(self.dir, self.nodename + '.pid')
		self.port = self.configuration.get_free_port()
		self.configfile = tempfile.mkstemp()[1]
		self.outputspoolfile = tempfile.mkstemp()[1]
		self.spoolfd = open(self.outputspoolfile, 'w')

		# Set up an environment.
		environment = {}
		environment['HOME'] = self.dir
		environment['RABBITMQ_BASE'] = self.dir
		environment['RABBITMQ_HOME'] = self.dir
		environment['RABBITMQ_MNESIA_BASE'] = self.dir
		environment['RABBITMQ_LOG_BASE'] = self.dir
		environment['RABBITMQ_NODENAME'] = self.nodename
		environment['RABBITMQ_PORT'] = str(self.port)
		environment['RABBITMQ_CONFIG_FILE'] = self.configfile

		# Set up a configuration file. (Needed to change the listening port)
		config = self.server_config % environment
		open(self.configfile + '.config', 'w').write(config)

		# Fire up the server.
		logging.info("Starting up rabbitmq server because requested by test.")
		self.process = subprocess.Popen([self.server_binary_path], env=environment,
			stdout=self.spoolfd, stderr=self.spoolfd)

		# As this takes a while, wait until it's started.
		checkfd = open(self.outputspoolfile, 'r')
		max_times = 30 # 6 seconds.
		self.started = False
		while not self.started and max_times > 0:
			checkfd.seek(0)
			contents = checkfd.read()
			if contents.find("broker running") != -1:
				# It's started.
				self.started = True
			else:
				# Wait a bit longer.
				max_times -= 1
				time.sleep(0.2)

		if not self.started:
			checkfd.seek(0)
			raise Exception("Failed to start RabbitMQ: " + checkfd.read())

	def get_client(self, io_loop=None, callback=None):
		credentials = pika.PlainCredentials('guest', 'guest')
		# This will connect immediately.
		parameters = pika.ConnectionParameters(host='localhost',
			port=self.port,
			virtual_host='/',
			credentials=credentials)
		self.client = TornadoConnection(parameters, on_open_callback=callback, io_loop=io_loop)
		# TODO: This supresses some warnings during unit tests, but maybe is not good for production.
		self.client.set_backpressure_multiplier(1000)
		return self.client

	def stop(self):
		if self.started:
			if self.client:
				self.client.close()
			# Clean up the server.
			pid = int(open(self.pidfile, 'r').read())
			os.kill(pid, signal.SIGTERM)
			os.unlink(self.configfile + '.config')
			os.unlink(self.outputspoolfile)
			shutil.rmtree(self.dir)

class TemporaryRabbitMQTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [])
		super(TemporaryRabbitMQTest, self).setUp()
		self.server = TemporaryRabbitMQ(self.configuration)
		# Basically, this shouldn't throw an exception.
		self.server.start()

	def tearDown(self):
		self.configuration.cleanup()
		super(TemporaryRabbitMQTest, self).tearDown()
		self.server.stop()

	def callback(self, channel, method, header, body):
		# Print out the message.
		#print body
		# Signal that we got it.
		self.stop()

	def test_basic(self):
		# Set up the client.
		client = self.server.get_client(io_loop=self.io_loop, callback=self.stop)
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

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.1, self.stop)
		self.wait()
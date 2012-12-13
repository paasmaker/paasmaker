
import tornado
import logging
import paasmaker
import time
import pika
import json
import uuid

from pubsub import pub

from ..testhelpers import TestHelpers

# TODO: Pubsub - handle errors.
# TODO: Pubsub - async ??

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class MessageExchange:
	def __init__(self, configuration):
		self.configuration = configuration
		self.job_status_queue_name = "queue-job-%s" % (id(self),)

	def setup(self, client, job_status_ready_callback=None):
		logger.debug("Message Broker (1): Connected. Opening channels.")
		self.client = client
		self.job_status_ready_callback = job_status_ready_callback
		self.client.channel(self.channel_open)

	def channel_open(self, channel):
		logger.debug("Message Broker (2): Channel open. Setting up Exchanges and queues.")
		# Now that the channel is open, declare the exchange.
		self.channel = channel
		# This one is for Job status. It's not durable, and is passed to all nodes.
		self.channel.exchange_declare(exchange='job.status', type='fanout', callback=self.on_job_status_exchange_open)

	def on_job_status_exchange_open(self, frame):
		logger.debug("Message Broker (3): Job status exchange is open.")
		self.channel.queue_declare(queue=self.job_status_queue_name, durable=False, callback=self.on_job_status_queue_declared)

	def on_job_status_queue_declared(self, frame):
		logger.debug("Message Broker (4): Job status queue is declared.")
		self.channel.queue_bind(exchange='job.status', queue=self.job_status_queue_name, routing_key='job.status', callback=self.on_job_status_queue_bound)

	def on_job_status_queue_bound(self, frame):
		logger.debug("Message Broker (6): Job status queue is bound, now consuming.")
		self.channel.basic_consume(consumer_callback=self.on_job_status_message, queue=self.job_status_queue_name)
		if self.job_status_ready_callback:
			self.job_status_ready_callback(self)
		# Subscribe to job status updates from internal, and pass them down the pipe...
		pub.subscribe(self.send_job_status, 'job.status')

	def on_job_status_message(self, channel, method, header, body):
		logger.debug("Job status incoming raw message: %s", body)
		# Parse the incoming message.
		parsed = json.loads(body)
		# TODO: validate against schema.
		# TODO: handle JSON decode errors.

		# If we're the originating node, don't broadcast it, because we already have seen it.
		if not self.configuration.get_node_uuid() == parsed['source']:
			self.configuration.send_job_status(parsed['job_id'], state=parsed['state'], source=parsed['source'])
		else:
			logger.debug("Dropping incoming job status message, as it was from our node originally.")

	def send_job_status(self, message):
		body = message.flatten()
		encoded = json.dumps(body)
		logger.debug("Sending job status message: %s", encoded)
		properties = pika.BasicProperties(content_type="application/json", delivery_mode=1)
		self.channel.basic_publish(exchange='job.status',
				routing_key='job.status',
				body=encoded,
				properties=properties)

class MessageExchangeTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(MessageExchangeTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(MessageExchangeTest, self).tearDown()

	def on_job_status_update(self, message):
		self.stop(message)

	def test_job_status(self):
		# Subscribe so we can catch the status update as it comes out.
		job_id = str(uuid.uuid4())
		pub.subscribe(self.on_job_status_update, self.configuration.get_job_status_pub_topic(job_id))

		# Set up our exchange.
		self.configuration.setup_message_exchange(self.stop, self.stop)

		# Wait for the system to be ready.
		result = self.wait(timeout=10)

		# Now send off a job update. This shouldn't actually touch the broker.
		self.configuration.send_job_status(job_id, state='TEST')
		status = self.wait()
		self.assertEquals(status.job_id, job_id, "Job ID was not as expected.")
		self.assertEquals(status.state, 'TEST', "Job status was not as expected.")

		# Now this time, force it to go through the exchange and back out again.
		message = paasmaker.common.configuration.JobStatusMessage(job_id, 'ROUNDTRIP', 'BOGUS')
		self.configuration.exchange.send_job_status(message)
		status = self.wait()
		self.assertEquals(status.job_id, job_id, "Job ID was not as expected.")
		self.assertEquals(status.state, 'ROUNDTRIP', "Job status was not as expected.")
		self.assertEquals(status.source, 'BOGUS', 'Source was correct.')


import tornado
import logging
import paasmaker
import time
import pika
import json
import uuid

from pubsub import pub

# TODO: Pubsub - handle errors.
# TODO: Pubsub - async ??

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class MessageExchange:
	def __init__(self, configuration):
		self.configuration = configuration
		self.job_status_queue_name = "queue-%s" % (id(self),)

	def setup(self, client, status_ready_callback=None, audit_ready_callback=None):
		logger.debug("Message Broker (1): Connected. Opening channels.")
		self.client = client
		self.status_ready_callback = status_ready_callback
		self.audit_ready_callback = audit_ready_callback
		self.client.channel(self.channel_open)

	def channel_open(self, channel):
		logger.debug("Message Broker (2): Channel open. Setting up Exchanges and queues.")
		# Now that the channel is open, declare the exchange.
		self.channel = channel
		# This one is for Job status. It's not durable, and is passed to all nodes.
		self.channel.exchange_declare(exchange='job.status', type='fanout', callback=self.on_job_status_exchange_open)

		if self.configuration.is_pacemaker():
			logger.debug("Message Broker (2): Opening job audit queue, as I'm a pacemaker.")
			# This one is for Job audit information. Only the pacemaker needs it. It is durable.
			self.channel.queue_declare(queue='job.audit', durable=True, callback=self.on_job_audit_queue_declared)

	def on_job_status_exchange_open(self, frame):
		logger.debug("Message Broker (3): Job status exchange is open.")
		self.channel.queue_declare(queue=self.job_status_queue_name, durable=False, callback=self.on_job_status_queue_declared)

	def on_job_status_queue_declared(self, frame):
		logger.debug("Message Broker (4): Job status queue is declared.")
		self.channel.queue_bind(exchange='job.status', queue=self.job_status_queue_name, routing_key='job.status', callback=self.on_job_status_queue_bound)

	def on_job_audit_queue_declared(self, frame):
		logger.debug("Message Broker (5): Job audit queue is declared, now consuming.")
		self.channel.basic_consume(consumer_callback=self.on_job_audit_message, queue='job.audit')
		if self.audit_ready_callback:
			self.audit_ready_callback(self)

	def on_job_status_queue_bound(self, frame):
		logger.debug("Message Broker (6): Job status queue is bound, now consuming.")
		self.channel.basic_consume(consumer_callback=self.on_job_status_message, queue=self.job_status_queue_name)
		if self.status_ready_callback:
			self.status_ready_callback(self)
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
			self.configuration.send_job_status(parsed['job_id'], parsed['state'], parsed['source'])
		else:
			logger.debug("Dropping incoming status message, as it was from our node originally.")

	def on_job_audit_message(self, channel, method, header, body):
		logger.debug("Job audit incoming raw message: %s", body)
		# Parse the message, and store in the database...
		# TODO: Test and implement.
		channel.basic_ack(delivery_tag=method.delivery_tag)

	def send_job_status(self, job_id, state, source):
		body = {'job_id': job_id, 'state': state, 'source': source}
		encoded = json.dumps(body)
		logger.debug("Sending job status message: %s", encoded)
		properties = pika.BasicProperties(content_type="application/json", delivery_mode=1)
		self.channel.basic_publish(exchange='job.status',
				routing_key='job.status',
				body = encoded,
				properties=properties)

	def send_audit_status(self, job_id, state):
		body = {'job_id': job_id, 'state': state}
		encoded = json.dumps(body)
		logger.debug("Sending job audit message: %s", encoded)
		properties = pika.BasicProperties(content_type="application/json", delivery_mode=2)
		self.channel.basic_publish(exchange='',
				routing_key='job.audit',
				body = encoded,
				properties=properties)

class MessageExchangeTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(MessageExchangeTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'])

	def tearDown(self):
		self.configuration.cleanup()
		super(MessageExchangeTest, self).tearDown()

	def on_job_status_update(self, job_id, state, source):
		self.stop({'job_id': job_id, 'state': state, 'source': source})

	def test_basic(self):
		# Subscribe so we can catch the status update as it comes out.
		job_id = str(uuid.uuid4())
		pub.subscribe(self.on_job_status_update, self.configuration.get_job_status_pub_topic(job_id))

		# Set up our exchange.
		self.configuration.setup_message_exchange(status_ready_callback=self.stop, audit_ready_callback=self.stop, io_loop=self.io_loop)

		# Wait twice for the system to be ready.
		self.wait()
		self.wait()

		# Now send off a job update. This shouldn't actually touch the broker.
		self.configuration.send_job_status(job_id, 'TEST')
		status = self.wait()
		self.assertEquals(status['job_id'], job_id, "Job ID was not as expected.")
		self.assertEquals(status['state'], 'TEST', "Job status was not as expected.")

		# Now this time, force it to go through the exchange and back out again.
		self.configuration.exchange.send_job_status(job_id, 'ROUNDTRIP', source="BOGUS")
		status = self.wait()
		self.assertEquals(status['job_id'], job_id, "Job ID was not as expected.")
		self.assertEquals(status['state'], 'ROUNDTRIP', "Job status was not as expected.")
		self.assertEquals(status['source'], 'BOGUS', 'Source was correct.')

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.1, self.stop)
		self.wait()

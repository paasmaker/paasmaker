from base import BaseWebsocketHandler
from base import BaseControllerTest

import paasmaker
import unittest
import tornado
import tornado.testing
import json
import uuid
import logging

import colander

from ws4py.client.tornadoclient import TornadoWebSocketClient

from pubsub import pub

# Send back log lines in batches of this size (bytes).
# TODO: Figure out a way to configure this. If we need to...
BLOCK_READ = 8192

# A schema for the type of message that this handler will accept.
class LogSubscribeSchema(colander.MappingSchema):
	position = colander.SchemaNode(colander.Integer(),
		title="Position to start",
		description="The position to start the subscription from. All data since this position is sent upon connection")
	job_id = colander.SchemaNode(colander.String(),
		title="Job ID",
		description="The ID of the job to work on")
class LogUnSubscribeSchema(colander.MappingSchema):
	job_id = colander.SchemaNode(colander.String(),
		title="Job ID",
		description="The ID of the job to work on")

class LogStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.NODE, BaseWebsocketHandler.USER]

	def open(self):
		self.last_positions = {}
		#print "Server: opened"
		pass

	def job_message_update(self, job_id=None):
		self.send_job_log(job_id, self.last_positions[job_id])

	def on_message(self, message):
		# Message should be JSON.
		parsed = self.parse_message(message)
		if parsed:
			if parsed['request'] == 'subscribe':
				self.handle_subscribe(parsed)
			if parsed['request'] == 'unsubscribe':
				self.handle_unsubscribe(parsed)

	def handle_subscribe(self, message):
		# Must match the subscribe schema.
		subscribe = self.validate_data(message, LogSubscribeSchema())
		if subscribe:
			if self.configuration.job_exists_locally(subscribe['job_id']):
				# Step 1: Feed since when they last saw.
				self.send_job_log(subscribe['job_id'], subscribe['position'])
				# Step 2: subscribe for future updates.
				pub.subscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(subscribe['job_id']))
				self.configuration.get_job_watcher().add_watch(subscribe['job_id'])

			elif self.configuration.is_pacemaker():
				# Find which node the job belongs to.
				# And then get that to stream the logs to us.
				# TODO: Implement!
				pass
			else:
				# TODO: Test that the error is sent!
				self.send_error('Unable to find job %s' % subscribe['job_id'], message)

	def handle_unsubscribe(self, message):
		# Must match the unsubscribe schema.
		unsubscribe = self.validate_data(message, LogUnSubscribeSchema())
		if unsubscribe:
			self.configuration.get_job_watcher().remove_watch(unsubscribe['job_id'])
			pub.unsubscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(unsubscribe['job_id']))

	def on_close(self):
		pass

	def make_data(self, job_id, log_lines, position):
		message = {
			'job_id': job_id,
			'lines': log_lines,
			'position': position
		}
		return message

	def send_job_log(self, job_id, last_position=0):
		log_file = self.configuration.get_job_log_path(job_id)

		fp = open(log_file, 'rb')
		if last_position > 0:
			fp.seek(last_position)
		lines = ['Dummy line']
		while len(lines) > 0:
			lines = fp.readlines(BLOCK_READ)
			self.send_success('lines', self.make_data(job_id, lines, fp.tell()))

		self.last_positions[job_id] = fp.tell()
		fp.close()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/log/stream", LogStreamHandler, configuration))
		return routes

class LogStreamHandlerTestClient(TornadoWebSocketClient):
	lines = []
	errors = []
	server_pos = 0
	job_id = ''
	configuration = None

	def opened(self):
		#print "Client: Opened!"
		pass

	def subscribe(self, job_id, position=0):
		data = { 'job_id': job_id, 'position': position }
		auth = { 'method': 'node', 'value': self.configuration.get_flat('node_token') }
		message = { 'request': 'subscribe', 'data': data, 'auth': auth }
		self.send(json.dumps(message))

	def unsubscribe(self, job_id):
		data = { 'job_id': job_id }
		auth = { 'method': 'node', 'value': self.configuration.get_flat('node_token') }
		message = { 'request': 'unsubscribe', 'data': data, 'auth': auth }
		self.send(json.dumps(message))

	def closed(self, code, reason=None):
		#print "Client: closed"
		pass

	def received_message(self, m):
		#print "Client: got %s" % m
		# Record the log lines.
		# CAUTION: m is NOT A STRING.
		parsed = json.loads(str(m))
		if parsed['type'] == 'lines':
			self.lines += parsed['data']['lines']
			self.server_pos = parsed['data']['position']
			self.job_id = parsed['data']['job_id']
		elif parsed['type'] == 'error':
			self.errors.append(parsed['data']['error'])

class LogStreamHandlerTest(BaseControllerTest):
	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = LogStreamHandler.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def setUp(self):
		# Call the parent setup...
		super(LogStreamHandlerTest, self).setUp()

		# Get the job logger, as we need to adjust a few things...
		self.logger = logging.getLogger('job')
		# Prevent propagation to the parent. This prevents extra messages
		# during unit tests.
		self.logger.propagate = False
		# Clean out all handlers. Otherwise multiple tests fail.
		self.logger.handlers = []
		# And set up the logger.
		paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(self.configuration)

	def tearDown(self):
		self.configuration.cleanup()

	def test_get_log(self):
		# Make a job number, and log to it.
		job_id = str(uuid.uuid4())
		number_lines = 10

		log = self.configuration.get_job_logger(job_id)

		for i in range(number_lines):
			log.info("Log message %d", i)

		path = self.configuration.get_job_log_path(job_id)

		# Now, connect to it and stream the log.
		client = LogStreamHandlerTestClient("ws://localhost:%d/log/stream" % self.get_http_port(), io_loop=self.io_loop)
		client.configuration = self.configuration
		client.connect()
		self.short_wait_hack() # Wait for connection to finish.

		client.subscribe(job_id)
		self.short_wait_hack() # Wait for server to send us the logs.

		#print str(client.lines)
		#print str(client.server_pos)
		#print str(client.errors)

		self.assertEquals(0, len(client.errors), "Errors found.")
		self.assertEquals(number_lines, len(client.lines), "Didn't download the expected number of lines.")

		#print str(client.lines)

		# Send another log entry.
		# This one should come back automatically because the websocket is
		# subscribed.
		log.info("Additional log entry.")

		self.short_wait_hack() # Wait for server to send us the logs.
		self.short_wait_hack() # We have to wait at most 200ms.
		self.short_wait_hack()

		self.assertEquals(0, len(client.errors), "Errors found.")
		self.assertEquals(number_lines + 1, len(client.lines), "Didn't download the expected number of lines.")

		# Unsubscribe.
		client.unsubscribe(job_id)

		self.short_wait_hack() # Wait for server to unsubscribe.

		# Send a new log entry. This one won't come back, because we've
		# unsubscribed.
		log.info("Another additional log entry.")

		# Now subscribe again. It will send us everything since the
		# end of the last subscribe.
		client.subscribe(job_id, position=client.server_pos)
		self.short_wait_hack() # Wait for server to send us the logs.

		self.assertEquals(0, len(client.errors), "Errors found.")
		self.assertEquals(number_lines + 2, len(client.lines), "Didn't download the expected number of lines.")

		#print str(client.lines)

		client.close()
		self.short_wait_hack() # Wait for closing.


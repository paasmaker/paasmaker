#!/usr/bin/env python

from base import BaseWebsocketHandler
from base import BaseControllerTest

import paasmaker
import unittest
import tornado
import tornado.testing
import json
import uuid
import logging

from ws4py.client.tornadoclient import TornadoWebSocketClient

from pubsub import pub

# Send back log lines in batches of this size (bytes).
# TODO: Figure out a way to configure this. If we need to...
BLOCK_READ = 8192

class LogStreamHandler(BaseWebsocketHandler):
	last_positions = {}

	def open(self):
		#print "Server: opened"
		pass

	def pub_msg_rcv(self, message=None, job_id=None):
		#print "Pub message!"
		#print message
		#print job_id
		self.write_message(self.make_message(job_id, [message], 1000))

	def on_message(self, message):
		# Message should be JSON.
		parsed = json.loads(message)
		# TODO: Enforce the message matching a schema.
		if parsed['request'] == 'subscribe':
			# Step 1: Feed since when they last saw.
			from_pos = 0
			if parsed.has_key('from_pos'):
				from_pos = parsed['from_pos']
			self.send_job_log(parsed['id'], from_pos)
			# Step 2: subscribe for future updates.
			pub.subscribe(self.pub_msg_rcv, self.configuration.get_job_pub_topic(parsed['id']))

	def on_close(self):
		pass

	def make_message(self, job_id, log_lines, position):
		message = {
			'type': 'lines',
			'id': job_id,
			'lines': log_lines,
			'position': position,
			'test': "Foo\nBar"
		}
		return self.encode_message(message)

	def send_job_log(self, job_id, last_position=0):
		log_file = self.configuration.get_job_log_path(job_id)
		fp = open(log_file, 'rb')
		if last_position > 0:
			fp.seek(last_position)
		lines = ['Dummy line']
		while len(lines) > 0:
			lines = fp.readlines(BLOCK_READ)
			message = self.make_message(job_id, lines, fp.tell())
			self.write_message(message)
		self.last_positions[job_id] = fp.tell()
		fp.close()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/log/stream", LogStreamHandler, configuration))
		return routes

class LogStreamHandlerTestClient(TornadoWebSocketClient):
	lines = []
	server_pos = 0
	job_id = ''

	def opened(self):
		#print "Client: Opened!"
		pass

	def subscribe(self, job_id, position=0):
		message = { 'request': 'subscribe', 'id': job_id, 'from_pos': position }
		self.send(json.dumps(message))

	def closed(self, code, reason=None):
		#print "Client: closed"
		pass

	def received_message(self, m):
		#print "Client: got %s" % m
		# Record the log lines.
		# CAUTION: m is NOT A STRING.
		parsed = json.loads(str(m))
		self.lines += parsed['lines']
		self.server_pos = parsed['position']
		self.job_id = parsed['id']

class LogStreamHandlerTest(BaseControllerTest):
	def get_app(self):
		routes = LogStreamHandler.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_torando_configuration())
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
		client.connect()
		self.short_wait_hack()
		self.wait() # Wait for connection to finish.

		client.subscribe(job_id)
		self.short_wait_hack()
		self.wait() # Wait for server to send us the logs.

		self.assertEquals(number_lines, len(client.lines), "Didn't download the expected number of lines.")

		# Send another log entry.
		# This one should come back automatically because the websocket is
		# subscribed.
		log.info("Additional log entry.")

		self.short_wait_hack()
		self.wait() # Wait for server to send us the logs.

		#print str(client.lines)
		#print str(client.server_pos)
		
		client.subscribe(job_id, position=client.server_pos)
		self.short_wait_hack()
		self.wait() # Wait for server to send us the logs.

		self.assertEquals(number_lines + 1, len(client.lines), "Didn't download the expected number of lines.")

		client.close()
		self.short_wait_hack()
		self.wait() # Wait for closing.

if __name__ == '__main__':
	tornado.testing.main()

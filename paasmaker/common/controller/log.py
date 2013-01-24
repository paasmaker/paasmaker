import unittest
import json
import uuid
import logging
import os

import paasmaker
from paasmaker.common.core import constants
from base import BaseWebsocketHandler
from base import BaseControllerTest
from base import BaseLongpollController

import tornado
import tornado.testing
import colander
from ws4py.client.tornadoclient import TornadoWebSocketClient
from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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
	unittest_force_remote = colander.SchemaNode(colander.Boolean(),
		title="Force remote job fetching",
		description="For unit tests only - force connecting to a remote node to simulate cross-host connections.",
		missing=False,
		default=False)

class LogUnSubscribeSchema(colander.MappingSchema):
	job_id = colander.SchemaNode(colander.String(),
		title="Job ID",
		description="The ID of the job to work on")

class LogStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.NODE, BaseWebsocketHandler.USER]

	def open(self):
		self.last_positions = {}
		self.subscribed = {}
		self.job_watcher = self.configuration.get_job_watcher()
		self.remote_connections = {}
		self.remote_subscriptions = {}
		logger.info("New connection to the log stream handler.")

	def job_message_update(self, job_id=None):
		logger.debug("New job data for %s, forwarding to client.", job_id)
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
			job_id = subscribe['job_id']
			logger.info("Handling subscribe request for %s", job_id)
			unittest_force_remote = subscribe['unittest_force_remote']
			if unittest_force_remote:
				logger.warning("Using unit test force-remote mode. SHOULD NOT APPEAR IN PRODUCTION.")

			def found_log(result_job_id, result):
				if isinstance(result, basestring):
					logger.info("Found job log %s locally.", job_id)
					# It's the path to the log.
					# Step 1: Feed since when they last saw.
					self.send_job_log(job_id, subscribe['position'])
					# Step 2: subscribe for future updates.
					pub.subscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(job_id))
					self.job_watcher.add_watch(job_id)
					self.subscribed[job_id] = True

				elif isinstance(result, paasmaker.model.Node):
					# It's a remote node containing the log.
					# Ie, the logs are in another Castle. Sorry Mario.
					self.handle_remote_subscribe(
						job_id,
						subscribe['position'],
						message,
						result,
						unittest_force_remote=unittest_force_remote
					)

			def unable_to_find_log(error_job_id, error_message):
				logger.error(error_message)
				self.send_error(error_message, message)

			# Find me a log file.
			self.configuration.locate_log(
				job_id,
				found_log,
				unable_to_find_log,
				unittest_force_remote=unittest_force_remote
			)

	def handle_remote_subscribe(self, job_id, position, message, node, unittest_force_remote=False):
		if not unittest_force_remote and node.uuid == self.configuration.get_node_uuid():
			# Prevent us from connecting to ourselves...
			self.send_success('zerosize', {'job_id': job_id})
			return

		if self.remote_connections.has_key(node.uuid):
			logger.debug("Using existing connection to %s", node.uuid)
			# We have an existing connection. Reuse that.
			remote = self.remote_connections[node.uuid]['connection']
			remote.subscribe(job_id)
			if not self.remote_subscriptions.has_key(job_id):
				# Don't increase the refcount if we subscribe multiple times.
				self.remote_connections[node.uuid]['refcount'] += 1
			self.remote_subscriptions[job_id] = node.uuid
		else:
			# No existing connection. Make one.
			logger.info("Creating connection to node %s", node.uuid)

			def this_remote_error(error):
				self.send_error("Error for job %s: %s" % (job_id, error), message)

			# Now we try to connect to it.
			# TODO: Test connection errors and handling of those errors.
			# Although we're already filtered to active instances,
			# so that will help a lot.
			logger.debug("Starting connection to %s", str(node))
			remote = LogStreamRemoteClient(
				"ws://%s:%d/log/stream" % (node.route, node.apiport),
				io_loop=self.configuration.io_loop
			)
			remote.configure(
				self.configuration,
				self.handle_remote_lines,
				this_remote_error
			)
			remote.subscribe(job_id, position=position)
			remote.connect()

			self.remote_connections[node.uuid] = {
				'connection': remote,
				'refcount': 1
			}

			self.remote_subscriptions[job_id] = node.uuid
			logger.debug("Now waiting for connection to %s", str(node))

	def handle_remote_lines(self, job_id, lines, position):
		logger.debug("Got %d lines from remote for %s.", len(lines), job_id)
		self.send_success('lines', self.make_data(job_id, lines, position))

	def handle_unsubscribe(self, message):
		# Must match the unsubscribe schema.
		unsubscribe = self.validate_data(message, LogUnSubscribeSchema())
		if unsubscribe:
			job_id = unsubscribe['job_id']
			logger.info("Handling unsubscribe request for %s", job_id)
			if self.subscribed.has_key(job_id):
				self.job_watcher.remove_watch(job_id)
				pub.unsubscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(job_id))
				del self.subscribed[job_id]
				logger.debug("Unsubscribed local follow for %s", job_id)
			if self.remote_subscriptions.has_key(job_id):
				nodeuuid = self.remote_subscriptions[job_id]
				del self.remote_subscriptions[job_id]
				logger.debug("Ref count for %s is %d", job_id, self.remote_connections[nodeuuid]['refcount'])
				self.remote_connections[nodeuuid]['refcount'] -= 1
				if self.remote_connections[nodeuuid]['refcount'] < 1:
					logger.info("Refcount for %s dropped to zero, closing connection.", nodeuuid)
					remote = self.remote_connections[nodeuuid]['connection']
					del self.remote_connections[nodeuuid]
					remote.close_connection()

	def on_close(self):
		logger.info("Connection closed.")
		logger.debug("Unsubscribing %d local subscriptions.", len(self.subscribed))
		for job_id in self.subscribed:
			self.job_watcher.remove_watch(job_id)
			pub.unsubscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(job_id))
		logger.debug("Closing %d remote connections.", len(self.remote_connections))
		for remote_uuid, remote_data in self.remote_connections:
			remote_data['connection'].close_connection()
		logger.debug("Closing complete.")

	def make_data(self, job_id, log_lines, position):
		message = {
			'job_id': job_id,
			'lines': log_lines,
			'position': position
		}
		return message

	def send_job_log(self, job_id, last_position=0):
		# TODO: If the log is huge, we won't want to stream the whole
		# thing, just the end of it. So only send back the last part of it,
		# regardless of where we requested the file from.
		log_file = self.configuration.get_job_log_path(job_id, create_if_missing=False)
		if os.path.getsize(log_file) == 0:
			# Report the zero size.
			# TODO: Unit test this.
			logger.debug("Sending zero size for %s", job_id)
			self.send_success('zerosize', {'job_id': job_id})
		else:
			logger.debug("Sending logs from %s, position %d", job_id, last_position)
			fp = open(log_file, 'rb')
			if last_position > 0:
				fp.seek(last_position)
			lines = ['Dummy line']
			while len(lines) > 0:
				lines = fp.readlines(BLOCK_READ)
				if len(lines) > 0:
					self.send_success('lines', self.make_data(job_id, lines, fp.tell()))

			self.last_positions[job_id] = fp.tell()
			fp.close()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/log/stream", LogStreamHandler, configuration))
		return routes

# TODO: Normal tornado stack context exception handling does not work if errors occur
# inside this client. Fix this.
class LogStreamRemoteClient(TornadoWebSocketClient):
	def configure(self, configuration, lines_callback, error_callback, unittest_force_remote=False):
		self.configuration = configuration
		self.connected = False
		self.lines_callback = tornado.stack_context.wrap(lines_callback)
		self.error_callback = tornado.stack_context.wrap(error_callback)
		self.startup_job_ids = []
		self.unittest_force_remote = unittest_force_remote

	def opened(self):
		self.connected = True
		logger.debug("Client: Remote connection open.")
		logger.debug("Client: Subscribing to %d jobs.", len(self.startup_job_ids))
		for meta in self.startup_job_ids:
			self.subscribe(meta['job_id'], meta['position'])
		self.startup_job_ids = []

	def subscribe(self, job_id, position=0):
		if not self.connected:
			logger.debug("Client: Not yet connected, queuing subscribe for %s", job_id)
			self.startup_job_ids.append({'job_id': job_id, 'position': position})
		else:
			logger.debug("Client: Sending subscribe request for %s", job_id)
			data = {'job_id': job_id, 'position': position, 'unittest_force_remote': self.unittest_force_remote}
			auth = {'method': 'node', 'value': self.configuration.get_flat('node_token')}
			message = {'request': 'subscribe', 'data': data, 'auth': auth}
			self.send(json.dumps(message))

	def unsubscribe(self, job_id):
		# TODO: Handle when unsubscribing when not connected.
		logger.debug("Client: Unsubscribing from %s", job_id)
		data = {'job_id': job_id}
		auth = {'method': 'node', 'value': self.configuration.get_flat('node_token')}
		message = {'request': 'unsubscribe', 'data': data, 'auth': auth}
		self.send(json.dumps(message))

	def closed(self, code, reason=None):
		logger.debug("Client: Closed.")
		self.connected = False

	def received_message(self, m):
		try:
			#print "Client: got %s" % m
			# Record the log lines.
			# CAUTION: m is NOT A STRING. We coerce it here before parsing it.
			parsed = json.loads(str(m))
			if parsed['type'] == 'lines':
				self.lines_callback(parsed['data']['job_id'], parsed['data']['lines'], parsed['data']['position'])
			elif parsed['type'] == 'error':
				self.error_callback(parsed['data']['error'])

		except Exception, ex:
			# We're kinda not on the tornado IO loop properly here,
			# so catch and report any errors.
			self.error_callback(str(ex), exception=ex)

class LogStreamHandlerTest(BaseControllerTest):
	config_modules = ['pacemaker']

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

		# Setup the job manager, for testing remote logs fetching.
		# Register sample jobs.
		self.configuration.plugins.register(
			'paasmaker.job.success',
			'paasmaker.common.job.manager.manager.TestSuccessJobRunner',
			{},
			'Test Success Job'
		)
		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		if hasattr(self, 'client'):
			self.client.close_connection()

		super(BaseControllerTest, self).tearDown()

	def test_get_log(self):
		# Make a job number, and log to it.
		job_id = str(uuid.uuid4())
		number_lines = 10

		log = self.configuration.get_job_logger(job_id)

		for i in range(number_lines):
			log.info("Log message %d", i)

		def got_lines(job_id, lines, position):
			logging.debug("Job ID: %s", job_id)
			logging.debug("Lines: %s", str(lines))
			logging.debug("Position: %d", position)
			# Store the last position on this function.
			got_lines.position = position
			self.stop(lines)

		# Now, connect to it and stream the log.
		self.client = LogStreamRemoteClient("ws://localhost:%d/log/stream" % self.get_http_port(), io_loop=self.io_loop)
		self.client.configure(self.configuration, got_lines, self.stop)
		self.client.subscribe(job_id)
		self.client.connect()

		lines = self.wait()

		self.assertEquals(number_lines, len(lines), "Didn't download the expected number of lines.")

		# Send another log entry.
		# This one should come back automatically because the websocket is subscribed.
		log.info("Additional log entry.")

		lines = self.wait()

		self.assertEquals(1, len(lines), "Didn't download the expected number of lines.")

		# Unsubscribe.
		self.client.unsubscribe(job_id)

		# Send a new log entry. This one won't come back, because we've unsubscribed.
		log.info("Another additional log entry.")
		log.info("And Another additional log entry.")

		# Now subscribe again. It will send us everything since the
		# end of the last subscribe.
		self.client.subscribe(job_id, position=got_lines.position)

		lines = self.wait()

		self.assertEquals(2, len(lines), "Didn't download the expected number of lines.")

	def test_no_job(self):
		# Make a job number, and log to it.
		job_id = str(uuid.uuid4())

		# Also, make us not a pacemaker for this one.
		# This is a hack...
		self.configuration['pacemaker']['enabled'] = False
		self.configuration.update_flat()

		# Now, connect to it and stream the log.
		self.client = LogStreamRemoteClient("ws://localhost:%d/log/stream" % self.get_http_port(), io_loop=self.io_loop)
		self.client.configure(self.configuration, self.stop, self.stop)
		self.client.subscribe(job_id)
		self.client.connect()

		error = self.wait()
		self.assertIn("not a pacemaker", error, "Error message is not as expected.")

	def test_get_remote(self):
		def got_lines(job_id, lines, position):
			logging.debug("Job ID: %s", job_id)
			logging.debug("Lines: %s", str(lines))
			logging.debug("Position: %d", position)
			# Store the last position on this function.
			got_lines.position = position
			self.stop(lines)

		# Give ourselves a node record.
		nodeuuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(nodeuuid)
		node = paasmaker.model.Node('test', 'localhost', self.get_http_port(), nodeuuid, constants.NODE.ACTIVE)
		session = self.configuration.get_database_session()
		session.add(node)
		session.commit()

		# Add a dummy job.
		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		job_id = self.wait()

		# Log to this dummy job a bit.
		number_lines = 10
		log = self.configuration.get_job_logger(job_id)
		for i in range(number_lines):
			log.info("Log message %d", i)

		# Now, connect to ourselves, and attempt to get it.
		self.client = LogStreamRemoteClient("ws://localhost:%d/log/stream" % self.get_http_port(), io_loop=self.io_loop)
		self.client.configure(self.configuration, got_lines, self.stop, unittest_force_remote=True)
		self.client.subscribe(job_id)
		self.client.connect()

		lines = self.wait()

		self.assertEquals(number_lines, len(lines), "Didn't download the expected number of lines.")

		# Unsubscribe, send more logs, then try again.
		self.client.unsubscribe(job_id)

		log.info("Another additional log entry.")
		log.info("And Another additional log entry.")

		self.client.subscribe(job_id, position=got_lines.position)

		lines = self.wait()

		self.assertEquals(2, len(lines), "Didn't download the expected number of lines.")

	def test_remote_instance_log(self):
		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			{},
			'1',
			'tornado-simple'
		)

		nodeuuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(nodeuuid)
		node = paasmaker.model.Node('test', 'localhost', self.get_http_port(), nodeuuid, constants.NODE.ACTIVE)
		session = self.configuration.get_database_session()
		session.add(node)
		session.commit()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(instance_type.id)

		instance = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			node
		)

		log = self.configuration.get_job_logger(instance.instance_id)
		log.info("Test instance output.")

		def got_lines(job_id, lines, position):
			logging.debug("Instance ID: %s", job_id)
			logging.debug("Lines: %s", str(lines))
			logging.debug("Position: %d", position)
			# Store the last position on this function.
			got_lines.position = position
			self.stop(lines)

		self.client = LogStreamRemoteClient("ws://localhost:%d/log/stream" % self.get_http_port(), io_loop=self.io_loop)
		self.client.configure(self.configuration, got_lines, self.stop, unittest_force_remote=True)
		self.client.subscribe(instance.instance_id)
		self.client.connect()

		lines = self.wait()

		self.assertEquals(len(lines), 1, "Didn't download the expected number of lines.")

		# Unsubscribe, send more logs, then try again.
		self.client.unsubscribe(instance.instance_id)

		log.info("Another additional log entry.")
		log.info("And Another additional log entry.")

		self.client.subscribe(instance.instance_id, position=got_lines.position)

		lines = self.wait()

		self.assertEquals(2, len(lines), "Didn't download the expected number of lines.")

		# Now try to subscibe to something that doesn't exist.
		noexist = str(uuid.uuid4())
		self.client.subscribe(noexist)

		# TODO: The subscribe above currently hangs. Fix this and test it.
		self.short_wait_hack()
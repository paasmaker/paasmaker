#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import os
import time
import unittest
import uuid

import paasmaker
from ...common.controller.base import BaseControllerTest
from paasmaker.common.core import constants

import tornado
from pubsub import pub
import tornadio2

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Send back log lines in batches of this size (bytes).
BLOCK_READ = 8192
MAX_LOG_SIZE = 102400 # Don't send back more logs than this size.

# TODO: Add hooks so that plugins can also use this connection.

class StreamConnection(tornadio2.SocketConnection):

	@tornado.gen.engine
	def on_open(self, request):
		"""
		Set up this stream connection, and set up storage variables used later.

		This also checks that the user is authorized.
		"""
		self.configuration = self.session.server.configuration

		def session_error_callback(message, exception=None):
			# Failed to get the session, which means no authentication.
			raise tornado.web.HTTPError(500, message)

		# AUTHORIZATION
		# Check that the user is allowed.
		self.authenticated = False
		self.auth_method = None
		if self.configuration.is_pacemaker():
			user_cookie_raw = request.get_cookie('user')
			if user_cookie_raw:
				# Decode the cookie.
				user_cookie_raw = user_cookie_raw.value
				tornado_settings = self.configuration.get_tornado_configuration()
				user_id = tornado.web.decode_signed_value(
					tornado_settings['cookie_secret'],
					'user',
					unicode(user_cookie_raw),
					max_age_days=self.configuration.get_flat('pacemaker.login_age')
				)

				if user_id:
					session = yield tornado.gen.Task(
						self.configuration.get_database_session,
						error_callback=session_error_callback
					)
					user = session.query(
						paasmaker.model.User
					).get(int(user_id))

					if user and user.enabled and not user.deleted:
						self.authenticated = True
						self.auth_method = 'user'
					session.close()

		auth_raw = request.get_argument('auth')
		if auth_raw:
			# Check against super token.
			if self.configuration.is_pacemaker() and auth_raw == self.configuration.get_flat('pacemaker.super_token'):
				self.authenticated = True
				self.auth_method = 'super'
			# And against the node token.
			if auth_raw == self.configuration.get_flat('node_token'):
				self.authenticated = True
				self.auth_method = 'node'
			# And against the user token.
			if self.configuration.is_pacemaker():
				session = yield tornado.gen.Task(
					self.configuration.get_database_session,
					error_callback=session_error_callback
				)
				user = session.query(
					paasmaker.model.User
				).filter(
					paasmaker.model.User.apikey == auth_raw
				).first()

				if user and user.enabled and not user.deleted:
					self.authenticated = True
					self.auth_method = 'user'
				session.close()

		# According to the docs, we're allowed to raise this to indicate to
		# the client that access is denied.
		if not self.authenticated:
			raise tornado.web.HTTPError(403, "Access denied.")

		# SETUP
		# Job setup.
		self.job_subscribed = {}
		self.job_listening = False

		# Log setup.
		self.log_last_positions = {}
		self.log_subscribed = {}
		self.log_job_watcher = self.configuration.get_job_watcher()
		self.log_remote_connections = {}
		self.log_remote_subscriptions = {}

		# Router setup.
		self.router_stats_queue = []

	def on_close(self):
		"""
		Clean up on connection or session closing.
		"""
		# Stop listening for job updates.
		if self.job_listening:
			pub.unsubscribe(self.on_job_status, 'job.status')
			self.job_listening = False

		# Clean up any logs listeners.
		logger.info("Connection closed.")
		logger.debug("Unsubscribing %d local subscriptions.", len(self.log_subscribed))
		for job_id in self.log_subscribed:
			self.log_job_watcher.remove_watch(job_id)
			pub.unsubscribe(self.log_message_update, self.configuration.get_job_message_pub_topic(job_id))
		logger.debug("Closing %d remote connections.", len(self.log_remote_connections))
		for remote_uuid, remote_data in self.log_remote_connections:
			remote_data['connection'].close_connection()
		logger.debug("Closing complete.")

		# Clean up router stats.
		if hasattr(self, 'router_stats_output') and self.router_stats_ready:
			self.router_stats_output.close()

	#
	# JOB HANDLING
	#

	def on_job_status(self, message):
		"""
		pubsub receiver for job status updates, which may get routed
		to the client based on their subscriptions.
		"""
		# pubsub receiver for job status messages.
		job_id = message.job_id
		parent_id = message.parent_id
		if self.job_subscribed.has_key(job_id):
			# Existing job that's subscribed - fetch and send a complete
			# status update to the client.
			def got_job_full(jobs):
				self.emit('job.status', job_id, jobs[job_id])

			# Fetch all the data.
			self.configuration.job_manager.get_jobs([message.job_id], got_job_full)

		elif parent_id and self.job_subscribed.has_key(parent_id):
			# Brand new job on an existing job that's been subscribed to.
			# Send that along to the client.
			def on_got_job(data):
				self.emit('job.new', data[job_id])

			self.configuration.job_manager.get_jobs([job_id], on_got_job)
			self.job_subscribed[message.job_id] = True

	@tornadio2.event('bounce')
	def bounce(self, message):
		self.emit('bounce', message)

	@tornadio2.event('job.subscribe')
	def job_subscribe(self, job_id):
		"""
		This event handler subscribes to the supplied job, and also
		the matching job tree. Future updates to this job and any jobs
		in the tree are automatically sent along to the client.

		The client is sent two messages: job.subscribed, with the entire
		job tree in flat format, and job.tree, which is the entire job
		tree in pretty format.
		"""
		if not self.configuration.is_pacemaker():
			# We don't relay job information if we're not a pacemaker.
			self.emit('error', 'This node is not a pacemaker.')
			return

		# Start listening to job status's after the first subscribe request.
		if not self.job_listening:
			pub.subscribe(self.on_job_status, 'job.status')
			self.job_listening = True

		def got_pretty_tree(tree):
			# Send back the pretty tree to the client.
			self.emit('job.tree', job_id, tree)

		def got_flat_tree_subscribe(job_ids):
			for job_id in job_ids:
				self.job_subscribed[job_id] = True
			self.emit('job.subscribed', list(job_ids))

		# Subscribe to everything in the tree.
		self.configuration.job_manager.get_pretty_tree(job_id, got_pretty_tree)
		self.configuration.job_manager.get_flat_tree(job_id, got_flat_tree_subscribe)

	@tornadio2.event('job.unsubscribe')
	def job_unsubscribe(self, job_id):
		"""
		Unsubscribe from the given job ID, and also the
		entire tree that it belongs to.
		"""
		if not self.configuration.is_pacemaker():
			# We don't relay job information if we're not a pacemaker.
			self.emit('error', 'This node is not a pacemaker.')
			return

		if not job_id in self.job_subscribed:
			# Take no action.
			return

		def got_flat_tree_unsubscribe(job_ids):
			for unsub_job_id in job_ids:
				del self.job_subscribed[unsub_job_id]
			self.emit('job.unsubscribed', job_ids)

		self.configuration.job_manager.get_flat_tree(job_id, got_flat_tree_unsubscribe)

	# LOG HANDLING

	def log_message_update(self, job_id=None):
		"""
		pubsub receiver for new log messages.
		"""
		logger.debug("New job data for %s, forwarding to client.", job_id)
		self.send_job_log(job_id, self.log_last_positions[job_id])

	@tornadio2.event('log.subscribe')
	def log_subscribe(self, job_id, position=0, unittest_force_remote=False):
		"""
		Subscribe to the given log, sending back data for that log as it's
		available.
		"""
		logger.info("Handling subscribe request for %s", job_id)

		if unittest_force_remote:
			logger.warning("Using unit test force-remote mode. SHOULD NOT APPEAR IN PRODUCTION.")

		if position is None:
			position = 0

		# Force into an int.
		position = int(position)

		def found_log(result_job_id, result):
			if isinstance(result, basestring):
				logger.info("Found job log %s locally.", job_id)

				read_position = position

				log_size = os.path.getsize(result)
				if log_size > MAX_LOG_SIZE:
					# Don't send back any more than MAX_LOG_SIZE of the file.
					# Yes, this will potentially chop log lines in half.
					# TODO: Make it not chop log lines in half.
					read_position = log_size - MAX_LOG_SIZE

				# It's the path to the log.
				# Step 1: Feed since when they last saw.
				self.send_job_log(job_id, read_position)
				# Step 2: subscribe for future updates.
				pub.subscribe(self.log_message_update, self.configuration.get_job_message_pub_topic(job_id))
				self.log_job_watcher.add_watch(job_id)
				self.log_subscribed[job_id] = True

			elif isinstance(result, paasmaker.model.Node):
				# It's a remote node containing the log.
				# Ie, the logs are in another Castle. Sorry Mario.
				self.handle_remote_subscribe(
					job_id,
					position,
					result,
					unittest_force_remote=unittest_force_remote
				)

		def unable_to_find_log(error_job_id, error_message):
			# Report this back to the client.
			self.emit('log.cantfind', error_job_id, error_message)

		# Find me a log file.
		self.configuration.locate_log(
			job_id,
			found_log,
			unable_to_find_log,
			unittest_force_remote=unittest_force_remote
		)

	def handle_remote_subscribe(self, job_id, position, node, unittest_force_remote=False):
		"""
		Helper function to handle fetching logs from a remote system via websocket.
		"""
		if not unittest_force_remote and node.uuid == self.configuration.get_node_uuid():
			# Prevent us from connecting to ourselves...
			self.emit('log.zerosize', job_id)
			return

		if self.log_remote_subscriptions.has_key(node.uuid):
			logger.debug("Using existing connection to %s", node.uuid)
			# We have an existing connection. Reuse that.
			remote = self.log_remote_subscriptions[node.uuid]['connection']
			remote.subscribe(job_id)
			if not self.log_remote_subscriptions.has_key(job_id):
				# Don't increase the refcount if we subscribe multiple times.
				self.log_remote_subscriptions[node.uuid]['refcount'] += 1
			self.log_remote_subscriptions[job_id] = node.uuid
		else:
			# No existing connection. Make one.
			logger.info("Creating connection to node %s", node.uuid)

			def remote_error(remote_job_id, error):
				self.emit('log.cantfind', remote_job_id, error)

			def remote_zerosize(job_id):
				self.emit('log.zerosize', job_id)

			# Now we try to connect to it.
			# TODO: Test connection errors and handling of those errors.
			# Although we're already filtered to active instances,
			# so that will help a lot.
			logger.debug("Starting connection to %s", str(node))
			remote = paasmaker.common.api.log.LogStreamAPIRequest(self.configuration)
			remote.set_target(node)
			remote.set_lines_callback(self.handle_remote_lines)
			remote.set_zerosize_callback(remote_zerosize)
			remote.set_cantfind_callback(remote_error)

			remote.subscribe(job_id, position=position)
			remote.connect()

			self.log_remote_connections[node.uuid] = {
				'connection': remote,
				'refcount': 1
			}

			self.log_remote_subscriptions[job_id] = node.uuid
			logger.debug("Now waiting for connection to %s", str(node))

	def handle_remote_lines(self, job_id, lines, position):
		"""
		pubsub receiver for log entries from a remote system.
		"""
		logger.debug("Got %d lines from remote for %s.", len(lines), job_id)
		self.emit('log.lines', job_id, lines, position)

	@tornadio2.event('log.unsubscribe')
	def log_unsubscribe(self, job_id):
		"""
		Unsubscribe from the given log, cleaning up any remote
		connections if needed.
		"""
		logger.info("Handling unsubscribe request for %s", job_id)
		if self.log_subscribed.has_key(job_id):
			self.log_job_watcher.remove_watch(job_id)
			pub.unsubscribe(self.log_message_update, self.configuration.get_job_message_pub_topic(job_id))
			del self.log_subscribed[job_id]
			logger.debug("Unsubscribed local follow for %s", job_id)
		if self.log_remote_subscriptions.has_key(job_id):
			nodeuuid = self.log_remote_subscriptions[job_id]
			del self.log_remote_subscriptions[job_id]
			logger.debug("Ref count for %s is %d", job_id, self.log_remote_connections[nodeuuid]['refcount'])
			self.log_remote_connections[nodeuuid]['refcount'] -= 1
			if self.log_remote_connections[nodeuuid]['refcount'] < 1:
				logger.info("Refcount for %s dropped to zero, closing connection.", nodeuuid)
				remote = self.log_remote_connections[nodeuuid]['connection']
				del self.log_remote_connections[nodeuuid]
				remote.close()

	def send_job_log(self, job_id, last_position=0):
		"""
		Helper function to send the local log from the given
		position onwards.

		:arg str job_id: The job ID.
		:arg int last_position: The position to stream from.
		"""
		log_file = self.configuration.get_job_log_path(job_id, create_if_missing=False)
		if os.path.getsize(log_file) == 0:
			# Report the zero size.
			# TODO: Unit test this.
			logger.debug("Sending zero size for %s", job_id)
			self.emit('log.zerosize', job_id)
		else:
			logger.debug("Sending logs from %s, position %d", job_id, last_position)
			fp = open(log_file, 'rb')
			if last_position > 0:
				fp.seek(last_position)
			lines = ['Dummy line']
			while len(lines) > 0:
				lines = fp.readlines(BLOCK_READ)
				if len(lines) > 0:
					self.emit('log.lines', job_id, lines, fp.tell())

			self.log_last_positions[job_id] = fp.tell()
			fp.close()

	#
	# ROUTER STATS HANDLING
	#

	def get_router_stats_handler(self, callback):
		"""
		Helper function to fetch the router stats output object.

		This function calls the callback with the stats output.
		Note that if this is called a few times, it may hold
		onto your callback for a short time, calling it when
		the object is finally available.
		"""
		def router_stats_error(error, exception=None):
			# Report the error back to the client.
			logger.error(error)
			if exception:
				logger.error("Exception:", exc_info=exception)

			self.router_stats_ready = False
			del self.router_stats_output
			self.emit('router.stats.error', error)

			# end of router_stats_error()

		def router_stats_ready():
			self.router_stats_ready = True

			# Call any other callbacks that were waiting.
			if len(self.router_stats_queue) > 0:
				for entry in self.router_stats_queue:
					entry(self.router_stats_output)
				self.router_stats_queue = []

			# end of router_stats_ready()

		if not self.configuration.is_pacemaker():
			# We don't relay job information if we're not a pacemaker.
			self.emit('error', 'This node is not a pacemaker.')
			return

		# See if we're connecting. If we are, queue up your request.
		if hasattr(self, 'router_stats_output') and self.router_stats_ready:
			# We have one and it's ready.
			callback(self.router_stats_output)

		elif hasattr(self, 'router_stats_output') and not self.router_stats_ready:
			# We're still connecting, so queue up your request.
			self.router_stats_queue.append(callback)

		else:
			# Set up the stats provider, as we don't have one.
			self.router_stats_output = paasmaker.router.stats.ApplicationStats(
				self.configuration
			)
			self.router_stats_queue.append(callback)
			self.router_stats_ready = False
			self.router_stats_output.setup(
				router_stats_ready,
				router_stats_error
			)

	@tornadio2.event('router.stats.update')
	def router_stats_update(self, name, input_id):
		"""
		Event to fetch a router stats update.
		"""
		def stats_ready(stats_output):
			def got_stats(stats):
				stats['as_at'] = time.time()
				self.emit('router.stats.update', name, input_id, stats)

			def failed_stats(error, exception=None):
				self.emit('router.stats.error', error, name, input_id)

			def got_set(vtset):
				stats_output.total_for_list('vt', vtset, got_stats, failed_stats)

			# Request some stats.
			# TODO: Check permissions!
			stats_output.vtset_for_name(
				name,
				int(input_id),
				got_set
			)
			# end of stats_ready()

		if not self.configuration.is_pacemaker():
			# We don't relay job information if we're not a pacemaker.
			self.emit('error', 'This node is not a pacemaker.')
			return

		self.get_router_stats_handler(stats_ready)

	@tornadio2.event('router.stats.history')
	def handle_history(self, name, input_id, metric, start, end=None):
		"""
		Event to fetch router history.

		:arg str metric: Either a string of one metric to fetch, or a list of metrics to
		    fetch. If metric is a string, returns an array of stats items (where each item
		    is a two-element array of unix timestamp and value). If metric is a list, the
		    return value will be a dict of arrays of stats items, keyed by metric name.
		"""
		if end is None:
			end = int(time.time())
		# TODO: Limit start/end to prevent DoS style attacks.

		def stats_ready(stats_output):
			aggregated_history = {}

			def failed_history(error, exception=None):
				self.emit('router.stats.error', error)

			def emit_history():
				self.emit(
					'router.stats.history',
					name,
					input_id,
					start,
					end,
					aggregated_history
				)

			def get_history_handler(current_metric, total_to_fetch):
				def got_history(history):
					aggregated_history[current_metric] = history
					if len(aggregated_history) == total_to_fetch:
						emit_history()
				return got_history

			def got_set(vtset):
				if isinstance(metric, basestring):
					metrics_to_query = [metric]
				else:
					metrics_to_query = metric

				for current_metric in metrics_to_query:
					stats_output.history(
						'vt',
						vtset,
						current_metric,
						get_history_handler(current_metric, len(metrics_to_query)),
						failed_history,
						start,
						end
					)

			# Request some stats.
			# TODO: Check permissions!
			stats_output.vtset_for_name(
				name,
				int(input_id),
				got_set
			)

			# end of stats_ready()

		if not self.configuration.is_pacemaker():
			# We don't relay router stats information if we're not a pacemaker.
			self.emit('error', 'This node is not a pacemaker.')
			return

		self.get_router_stats_handler(stats_ready)




class StreamConnectionTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = []

		socketio_router = tornadio2.TornadioRouter(
			paasmaker.pacemaker.controller.stream.StreamConnection
		)
		# Hack to store the configuration on the socket.io router.
		socketio_router.configuration = self.configuration

		application_settings = self.configuration.get_tornado_configuration()
		application = tornado.web.Application(
			socketio_router.apply_routes(routes),
			**application_settings
		)

		return application

	def setUp(self):
		# Call the parent setup...
		super(StreamConnectionTest, self).setUp()

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

		# Register sample jobs for the jobs stream tests.
		self.configuration.plugins.register(
			'paasmaker.job.success',
			'paasmaker.common.job.manager.manager.TestSuccessJobRunner',
			{},
			'Test Success Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.failure',
			'paasmaker.common.job.manager.manager.TestFailJobRunner',
			{},
			'Test Fail Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.aborted',
			'paasmaker.common.job.manager.manager.TestAbortJobRunner',
			{},
			'Test Abort Job'
		)

		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		if hasattr(self, 'client'):
			self.client.close()

		super(StreamConnectionTest, self).tearDown()

	def test_no_job(self):
		# Make a job number, and log to it.
		job_id = str(uuid.uuid4())

		# Also, make us not a pacemaker for this one.
		# This is a hack...
		self.configuration['pacemaker']['enabled'] = False
		self.configuration.update_flat()

		def no_job(job_id, message):
			self.stop(message)

		# Now, connect to it and stream the log.
		self.client = paasmaker.common.api.log.LogStreamAPIRequest(self.configuration)
		self.client.set_cantfind_callback(no_job)
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
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
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
		self.client = paasmaker.common.api.log.LogStreamAPIRequest(self.configuration)
		self.client.set_lines_callback(got_lines)
		self.client.subscribe(job_id, None, True)

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
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
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

		self.client = paasmaker.common.api.log.LogStreamAPIRequest(self.configuration)
		self.client.set_lines_callback(got_lines)
		self.client.subscribe(instance.instance_id, None, True)

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
		def cantfind(job_id, message):
			self.stop(message)

		self.client.set_cantfind_callback(cantfind)

		noexist = str(uuid.uuid4())
		self.client.subscribe(noexist)

		message = self.wait()

		self.assertIn("No such job", message, "Error message not as expected.")

	def test_get_log(self):
		# Test the websocket version.
		self._test_get_log(False)
		# Test the longpoll version.
		self._test_get_log(True)

	def _test_get_log(self, force_longpoll):
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

		def on_error(error):
			print error

		# Now, connect to it and stream the log.
		remote_request = paasmaker.common.api.log.LogStreamAPIRequest(self.configuration, force_longpoll=force_longpoll)
		remote_request.set_superkey_auth()
		remote_request.set_lines_callback(got_lines)
		remote_request.subscribe(job_id)

		remote_request.connect()

		lines = self.wait()

		self.assertEquals(number_lines, len(lines), "Didn't download the expected number of lines.")

		# Send another log entry.
		# This one should come back automatically because the websocket is subscribed.
		log.info("Additional log entry.")

		lines = self.wait()

		self.assertEquals(1, len(lines), "Didn't download the expected number of lines.")

		# Unsubscribe.
		remote_request.unsubscribe(job_id)

		# Send a new log entry. This one won't come back, because we've unsubscribed.
		log.info("Another additional log entry.")
		log.info("And Another additional log entry.")

		# Now subscribe again. It will send us everything since the
		# end of the last subscribe.
		remote_request.subscribe(job_id, position=got_lines.position)

		lines = self.wait()

		self.assertEquals(2, len(lines), "Didn't download the expected number of lines.")

	def test_job_stream(self):
		# Test the websocket version.
		self._test_job_stream(False)
		# And then the long poll version.
		self._test_job_stream(True)

	def _test_job_stream(self, force_longpoll):
		def job_subscribed(jobs):
			self.stop(('subscribed', jobs))

		def job_new(data):
			self.stop(('new', data))

		def job_tree(job_id, tree):
			self.stop(('tree', tree))

		def job_status(job_id, data):
			self.stop(('status', data))

		remote = paasmaker.common.api.job.JobStreamAPIRequest(self.configuration, force_longpoll=force_longpoll)
		remote.set_superkey_auth()

		remote.set_subscribed_callback(job_subscribed)
		remote.set_status_callback(job_status)
		remote.set_new_callback(job_new)
		remote.set_tree_callback(job_tree)

		remote.connect()

		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()

		remote.subscribe(root_id)

		# TODO: Make these tests more exhaustive.
		def lose_the_job_id(job_id):
			pass

		# We don't know what order tree/subscribed will come back in,
		# so either is acceptable - as long as we get two of them.
		response = self.wait()
		self.assertIn(response[0], ['tree', 'subscribed'], 'Wrong response.')
		response = self.wait()
		self.assertIn(response[0], ['tree', 'subscribed'], 'Wrong response.')

		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", lose_the_job_id, parent=root_id, tags=['test'])
		self.manager.add_job('paasmaker.job.success', {}, "Example sub2 job.", lose_the_job_id, parent=root_id)

		# Start processing them.
		self.manager.allow_execution(root_id)

		expected_types = ['new', 'status']
		expected_qty = 6

		for i in range(expected_qty):
			response = self.wait()
			self.assertIn(response[0], expected_types, 'Wrong response - got %s.' % response[0])

	def test_router_stream(self):
		# Test the websocket version.
		self._test_router_stream(False)
		# And then the longpoll version.
		self._test_router_stream(True)

	def _test_router_stream(self, force_longpoll):
		def history(name, input_id, start, end, values):
			self.stop(('history', name, input_id, start, end, values))

		def update(name, input_id, values):
			self.stop(('update', name, input_id, values))

		def error(message, exception=None, name=None, input_id=None):
			#print message
			self.stop(('error', message))

		remote = paasmaker.common.api.router.RouterStreamAPIRequest(self.configuration, force_longpoll=force_longpoll)
		remote.set_superkey_auth()

		remote.set_history_callback(history)
		remote.set_update_callback(update)
		remote.set_stats_error_callback(error)

		remote.connect()

		# Ask for updates.
		remote.stats('workspace', 1)
		response = self.wait()
		self.assertEquals(response[0], 'error', "Wrong response - got %s." % response[0])

		remote.stats('version_type', 1)
		response = self.wait()
		self.assertEquals(response[0], 'update', "Wrong response - got %s." % response[0])

		remote.history('workspace', 1, 'requests', time.time() - 60)
		response = self.wait()
		self.assertEquals(response[0], 'history', "Wrong response - got %s." % response[0])

		remote.history('version_type', 1, 'requests', time.time() - 60)
		response = self.wait()
		self.assertEquals(response[0], 'history', "Wrong response - got %s." % response[0])

		remote.history('workspace', 1, 'requests', time.time() - 60, time.time())
		response = self.wait()
		self.assertEquals(response[0], 'history', "Wrong response - got %s." % response[0])

		remote.history('version_type', 1, 'requests', time.time() - 60, time.time())
		response = self.wait()
		self.assertEquals(response[0], 'history', "Wrong response - got %s." % response[0])

import logging
import os
import time

import paasmaker

import tornado
from pubsub import pub
import tornadio2

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Send back log lines in batches of this size (bytes).
BLOCK_READ = 8192

# TODO: Add hooks so that plugins can also use this connection.

class StreamConnection(tornadio2.SocketConnection):

	def on_open(self, request):
		"""
		Set up this stream connection, and set up storage variables used later.

		This also checks that the user is authorized.
		"""
		self.configuration = self.session.server.configuration

		# AUTHORIZATION
		# Check that the user is allowed.
		self.authenticated = False
		user_cookie_raw = request.get_cookie('user').value
		if user_cookie_raw:
			# Decode the cookie.
			tornado_settings = self.configuration.get_tornado_configuration()
			user_id = tornado.web.decode_signed_value(
				tornado_settings['cookie_secret'],
				'user',
				unicode(user_cookie_raw),
				max_age_days=self.configuration.get_flat('pacemaker.login_age')
			)

			if user_id:
				session = self.configuration.get_database_session()
				user = session.query(
					paasmaker.model.User
				).get(int(user_id))

				if user and user.enabled and not user.deleted:
					self.authenticated = True
				session.close()

		auth_raw = request.get_argument('auth')
		if auth_raw:
			# Check against super token. No other auth is supported.
			if auth_raw == self.configuration.get_flat('pacemaker.super_token'):
				self.authenticated = True

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
				self.send_success('job.new', data[job_id])

			self.configuration.job_manager.get_jobs([job_id], on_got_job)
			self.job_subscribed[message.job_id] = True

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

		def found_log(result_job_id, result):
			if isinstance(result, basestring):
				logger.info("Found job log %s locally.", job_id)
				# It's the path to the log.
				# Step 1: Feed since when they last saw.
				self.send_job_log(job_id, position)
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

			def this_remote_error(error):
				self.emit('log.error', job_id, error)

			# Now we try to connect to it.
			# TODO: Test connection errors and handling of those errors.
			# Although we're already filtered to active instances,
			# so that will help a lot.
			# TODO: Switch this to using socket.io to connect to remote nodes.
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
		"""
		# TODO: If the log is huge, we won't want to stream the whole
		# thing, just the end of it. So only send back the last part of it,
		# regardless of where we requested the file from.
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

		def router_stats_ready():
			self.router_stats_ready = True

			# Call any other callbacks that were waiting.
			if len(self.router_stats_queue) > 0:
				for entry in self.router_stats_queue:
					entry(self.router_stats_output)
				self.router_stats_queue = []

			# Plus the one that kicked this one off.
			callback(self.router_stats_output)

		# See if we're connecting. If we are,
		# queue up your request.
		if hasattr(self, 'router_stats_output') and not self.router_stats_ready:
			self.router_stats_queue.append(callback)

		else:
			# Set up the stats provider.
			self.router_stats_output = paasmaker.router.stats.ApplicationStats(
				self.configuration
			)
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
				self.emit('router.stats.error', error)

			def got_set(vtset):
				stats_output.total_for_list('vt', vtset, got_stats, failed_stats)

			# Request some stats.
			# TODO: Check permissions!
			stats_output.vtset_for_name(
				name,
				int(input_id),
				got_set
			)

		self.get_router_stats_handler(stats_ready)

	@tornadio2.event('router.stats.history')
	def handle_history(self, name, input_id, metric, start, end=None):
		"""
		Event to fetch router history. Returns a set of points that
		match the requested input.
		"""
		if end is None:
			end = int(time.time())

		def stats_ready(stats_output):

			def got_history(history):
				self.emit(
					'router.stats.history',
					name,
					input_id,
					start,
					end,
					history
				)

			def failed_history(error, exception=None):
				self.emit('router.stats.error', error)

			def got_set(vtset):
				stats_output.history(
					'vt',
					vtset,
					metric,
					got_history,
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

		self.get_router_stats_handler(stats_ready)
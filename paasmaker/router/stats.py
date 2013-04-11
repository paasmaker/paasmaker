#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import json
import logging
import time

import paasmaker
from paasmaker.common.core import constants

import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READ_SIZE_BATCH = 8192 # Read this many bytes/lines in one go.

class StatsLogReader(object):
	"""
	A class to read a specially formatted NGINX access log,
	and write the results into a Redis instance. This is designed
	to return real time data on applications running on the cluster.
	"""
	def __init__(self, configuration):
		self.configuration = configuration
		self.reading = False
		self.records = {}
		self.hashrecords = {}
		self.position = None

	def _get_position_key(self):
		return "position:%s" % self.configuration.get_node_uuid()

	def read(self, callback, error_callback):
		"""
		Read the log file from the last position it was read from,
		and insert the records into the stats redis.

		When done, it will call the callback with a message.
		If it fails, it will call the error_callback instead.

		:arg callable callback: The callback to invoke upon
			success.
		:arg callable error_callback: The callback to invoke
			upon an error.
		"""
		if self.reading:
			# Already reading, so don't start reading again.
			callback("Still reading.")
			return
		else:
			self.reading = True
			self.records = {}
			self.hashrecords = {}

		# Check quickly first if we can without hitting redis
		# if the file has changed.
		filename = self.configuration.get_flat('router.stats_log')
		size = os.path.getsize(filename)
		if size == self.position:
			self.reading = False
			callback("Not changed.")
			return
		else:
			self.position = size

		# Now continue.

		# Fetch the stats redis instance.
		self.callback = callback
		self.error_callback = error_callback
		self.configuration.get_stats_redis(self._got_redis, error_callback)

	def _got_redis(self, redis):
		# First query the last position we were up to.
		self.redis = redis
		self.redis.get(self._get_position_key(), self._got_position)

	def _got_position(self, position):
		if not position:
			position = 0
		position = int(position)

		# Open the file, seek to that position, and start reading.
		filename = self.configuration.get_flat('router.stats_log')
		size = os.path.getsize(filename)

		if position > size:
			# Log file must have been rotated.
			# TODO: We might have lost stats here.
			position = 0

		if position == size:
			# Nothing's changed. No need to read the file at all.
			self.reading = False
			self.callback("No new log entries.")
		else:
			logger.debug("Starting to read %s from position %d.", filename, position)
			self.fp = open(filename, 'r')
			if position > 0:
				self.fp.seek(position)
			self.batches_read = 0
			self._read_batch()

	def _read_batch(self):
		# Read in a batch.
		if self.batches_read > 10:
			# If we've read more than 10 batches this pass,
			# just flush that to Redis and then come back later.
			# This prevents the scenario where we're several
			# hundred megabytes of logs behind and we try to
			# read all of that into memory to start with...
			self._finalize_batch()
		else:
			batch = self.fp.readlines(READ_SIZE_BATCH)
			self.batches_read += 1
			logger.debug("%d lines in this batch.", len(batch))
			if len(batch) == 0:
				self._finalize_batch()
			else:
				# Process this batch.
				self._process_batch(batch)

	def _process_batch(self, lines):
		# Parse them all.
		for line in lines:
			try:
				parsed = json.loads(line)
				vt_id = parsed['version_type_key']
				if vt_id == '':
					# Bad key. Just reset it.
					vt_id = 'null'

				vt_key = 'stat_vt:%s' % vt_id

				node_id = parsed['node_key']
				node_key = None
				if node_id == '' or node_id == 'null':
					# Bad key. Don't log anything.
					node_id = None
				else:
					node_key = 'stat_node:%s' % node_id

				# Basic stats.
				self._store_hash_value(vt_key, 'requests', 1)
				self._store_hash_value(vt_key, 'bytes', parsed['bytes'])

				if node_key:
					self._store_hash_value(node_key, 'requests', 1)
					self._store_hash_value(node_key, 'bytes', parsed['bytes'])

				# The upstream response time, if given.
				if parsed['upstream_response_time'] != '-':
					# Convert it into decimal milliseconds.
					upstream_response_milliseconds = int(float(parsed['upstream_response_time']) * 1000)

					self._store_hash_value(vt_key, 'time', upstream_response_milliseconds)
					self._store_hash_value(vt_key, 'timecount', 1)

					if node_key:
						self._store_hash_value(node_key, 'time', upstream_response_milliseconds)
						self._store_hash_value(node_key, 'timecount', 1)

				# nginx's own time, converted into decimal milliseconds.
				nginx_time_milliseconds = int(float(parsed['nginx_response_time']) * 1000)
				self._store_hash_value(vt_key, 'nginxtime', nginx_time_milliseconds)

				if node_key:
					self._store_hash_value(node_key, 'nginxtime', nginx_time_milliseconds)

				# Split the response code into categories.
				code_category = "%dxx" % (parsed['code'] / 100)
				self._store_hash_value(vt_key, code_category, 1)

				if node_key:
					self._store_hash_value(node_key, code_category, 1)

				# But why not, let's store the exact code too! It's quite cheap.
				self._store_hash_value(vt_key, parsed['code'], 1)

				if node_key:
					self._store_hash_value(node_key, parsed['code'], 1)

				# For graphs. The target keys are like this:
				# history:<vtid>:NNNNNNNNN:requests
				# Where NNNNNNN is the unix time in seconds at the top of the hour.
				# The key type is a hash.
				hour_top = parsed['timemsec'] - (parsed['timemsec'] % 3600)
				history_prefix_vt = "history_vt:%s:%d" % (vt_id, hour_top)
				history_prefix_node = None
				if node_key:
					history_prefix_node = "history_node:%s:%d" % (node_id, hour_top)

				# And co-orce this one into an int.
				history_key = "%d" % parsed['timemsec']

				# Basic stats.
				self._store_hash_value("%s:requests" % history_prefix_vt, history_key, 1)
				self._store_hash_value("%s:bytes" % history_prefix_vt, history_key, parsed['bytes'])

				if history_prefix_node:
					self._store_hash_value("%s:requests" % history_prefix_node, history_key, 1)
					self._store_hash_value("%s:bytes" % history_prefix_node, history_key, parsed['bytes'])

				# Upstream response time and count.
				if parsed['upstream_response_time'] != '-':
					# Convert it into decimal milliseconds.
					self._store_hash_value("%s:time" % history_prefix_vt, history_key, upstream_response_milliseconds)
					self._store_hash_value("%s:timecount" % history_prefix_vt, history_key, 1)

					if history_prefix_node:
						self._store_hash_value("%s:time" % history_prefix_node, history_key, upstream_response_milliseconds)
						self._store_hash_value("%s:timecount" % history_prefix_node, history_key, 1)

				# Response code.
				self._store_hash_value("%s:%s" % (history_prefix_vt, code_category), history_key, 1)

				if history_prefix_node:
					self._store_hash_value("%s:%s" % (history_prefix_node, code_category), history_key, 1)

				# nginx's own time, converted into decimal milliseconds.
				self._store_hash_value("%s:nginxtime" % history_prefix_vt, history_key, nginx_time_milliseconds)

				if history_prefix_node:
					self._store_hash_value("%s:nginxtime" % history_prefix_node, history_key, nginx_time_milliseconds)

			except ValueError, ex:
				# Invalid line. Skip it.
				logger.error("Invalid line '%s', ignoring.", line)
			except KeyError, ex:
				# Malformed line.
				logger.error("Malformed line from '%s', ignoring.", parsed)

		# Read the next batch.
		# Do it on the IO loop, so it cooperates with other things.
		self.configuration.io_loop.add_callback(self._read_batch)

	def _store_value(self, key, metric, value):
		# Helper function to store a value in the records
		# set, for insertion later. Adds the current value
		# if it doesn't exist, or creates the key otherwise.
		# TODO: No longer in use...
		final_key = "stat_vt:%s:%s" % (key, metric)
		if self.records.has_key(final_key):
			self.records[final_key] += value
		else:
			self.records[final_key] = value

	def _store_hash_value(self, bucket, key, value):
		# Helper function to store the key in the given
		# bucket, creating that bucket or key if needed,
		# or otherwise summing previous results.
		if not self.hashrecords.has_key(bucket):
			self.hashrecords[bucket] = {}
		if not self.hashrecords[bucket].has_key(key):
			self.hashrecords[bucket][key] = 0

		self.hashrecords[bucket][key] += value

	def _finalize_batch(self):
		# Finalize the batch, by inserting it into the Redis
		# instance.
		position = self.fp.tell()
		logger.debug("Completed reading up to position %d", position)
		logger.debug("Recording %d stats.", len(self.records))
		pipeline = self.redis.pipeline(True)
		for key, value in self.records.iteritems():
			pipeline.incrby(key, value)
		for bucket, keyset in self.hashrecords.iteritems():
			for key, value in keyset.iteritems():
				pipeline.hincrby(bucket, key, amount=value)
		pipeline.set(self._get_position_key(), position)
		self.position = position
		pipeline.execute(self._batch_finalized)

	def _batch_finalized(self, result):
		logger.info("Completed writing stats to redis.")
		self.fp.close()
		self.reading = False
		self.redis.disconnect()
		self.callback("Completed reading file.")

class StatsLogPeriodicManager(object):
	"""
	A helper class to manage periodically reading the access log
	and invoking the log reader to write to Redis.
	"""
	def __init__(self, configuration):
		# First, the log reader.
		self.log_reader = StatsLogReader(configuration)
		# Then the periodic callback handler.
		self.periodic = tornado.ioloop.PeriodicCallback(
			self.read_stats,
			configuration.get_flat('router.stats_interval'),
			io_loop=configuration.io_loop
		)

	def start(self):
		"""
		Start the periodic manager to read stats.
		"""
		self.periodic.start()

	def read_stats(self):
		"""
		Read the stats right now.
		"""
		# Attempt to read the stats.
		self.log_reader.read(self._on_complete, self._on_error)

	def _on_complete(self, message):
		# Do nothing, it's already been logged.
		#logger.info(message)
		pass

	def _on_error(self, error, exception=None):
		# Log the error, but allow it to try again next time.
		logger.error(error)
		if exception:
			lgoger.error(exc_info=exception)

class ApplicationStats(object):
	"""
	Read out the router stats for applications.

	The core goal of this class is to aggregate where it
	needs to. Stats are recorded down to the application version
	type level. However, it is often desirable to then show
	all stats for an application version, application, or workspace,
	and this class is primary responsible for handling that aggregation.

	In the code and the documentation, the abbreviation "vtset" refers
	to a set of version type IDs that should be aggregated to give the
	result. The stats redis already stores sets of version type IDs for
	various containers; such as the workspace.
	"""

	# CAUTION: This list MUST match the length and order in the stats_standard.lua
	# file. Otherwise they will get mismatched.
	METRICS = [
		'bytes',
		'1xx',
		'1xx_percentage',
		'2xx',
		'2xx_percentage',
		'3xx',
		'3xx_percentage',
		'4xx',
		'4xx_percentage',
		'5xx',
		'5xx_percentage',
		'requests',
		'time',
		'timecount',
		'time_average',
		'nginxtime',
		'nginxtime_average'
	]

	@classmethod
	def load_redis_scripts(cls, configuration, callback, error_callback):
		# Load the scripts required for the stats into the stats Redis.
		scripts = ['stats_standard.lua', 'stats_history.lua']
		script_path = os.path.normpath(os.path.dirname(__file__))

		def got_redis(client):
			def load_script():
				try:
					script = scripts.pop()
					full_path = os.path.join(script_path, script)

					def script_loaded(sha1):
						if isinstance(sha1, paasmaker.thirdparty.tornadoredis.exceptions.ResponseError):
							error_callback("Failed to load script %s: %s" % (script, str(sha1)))
							return

						# Store the SHA1 for later.
						configuration.redis_scripts[script] = sha1

						# Load the next script.
						load_script()

						# end of script_loaded()

					body = open(full_path, 'r').read()

					client.script_load(body, script_loaded)

				except IndexError, ex:
					# No more to insert.
					callback("Completed inserting stats scripts.")
				# end of load_script()

			load_script()
			# end of got_redis()

		configuration.get_stats_redis(got_redis, error_callback)

	def __init__(self, configuration):
		self.configuration = configuration

	def setup(self, callback, error_callback):
		"""
		Set up this stats object so it can fetch
		stats. Calls the callback when it is ready
		to be used.

		:arg callable callback: The callback to call
			when ready.
		:arg callable error_callback: The callback to
			call when unable to get ready.
		"""
		self.ready_callback = callback
		self.configuration.get_stats_redis(
			self._redis_ready,
			error_callback
		)

	def _redis_ready(self, redis):
		self.redis = redis
		self.ready_callback()

	def close(self):
		"""
		Close the attached Redis connection and any other resources.
		"""
		self.redis.disconnect()

	def permission_required_for(self, name, input_id, session):
		"""
		From the supplied name and input ID, find the permission name
		and workspace that you need to check permissions against before
		fetching the stats.

		Returns a tuple, with (exists, PERMISSION_NAME, workspace_id).
		``exists`` is a boolean flag that indicates if the target exists
		or not.

		:arg str name: The name of the stat to fetch.
		:arg str|int input_id: The input ID that matches the stat.
		:arg Session session: An active SQLAlchemy session to do
			lookups in.
		"""
		exists = False
		permission = None
		workspace_id = None

		if name == 'workspace':
			# Look up the workspace in the DB.
			workspace = session.query(
				paasmaker.model.Workspace
			).get(int(input_id))

			if workspace is not None:
				workspace_id = workspace.id
				exists = True
				permission = constants.PERMISSION.WORKSPACE_VIEW

		elif name == 'application':
			# Look up the application.
			application = session.query(
				paasmaker.model.Application
			).get(int(input_id))

			if application is not None:
				workspace_id = application.workspace.id
				exists = True
				permission = constants.PERMISSION.WORKSPACE_VIEW

		elif name == 'version':
			# Look up the version.
			version = session.query(
				paasmaker.model.ApplicationVersion
			).get(int(input_id))

			if version is not None:
				workspace_id = version.application.workspace.id
				exists = True
				permission = constants.PERMISSION.WORKSPACE_VIEW

		elif name == 'version_type':
			# Look up the version type.
			version_type = session.query(
				paasmaker.model.ApplicationInstanceType
			).get(int(input_id))

			if version_type is not None:
				workspace_id = version_type.application_version.application.workspace.id
				exists = True
				permission = constants.PERMISSION.WORKSPACE_VIEW

		elif name == 'uncaught' or name == 'pacemaker':
			# Requires SYSTEM_OVERVIEW
			exists = True
			permission = constants.PERMISSION.SYSTEM_OVERVIEW

		return (exists, permission, workspace_id)

	def stats_for_name(self, name, input_id, callback, listtype='vt'):
		"""
		Fetch the router stats for the given input name and ID.

		Name is one of a few options of aggregated sets
		to return. ``input_id`` then selects the specific
		aggregation.

		Name can be one of the following:

		* **workspace**: all the version type IDs in the
		  specified workspace.
		* **application**: all the version type IDs in the
		  specified application.
		* **version**: all the version type IDs in the specified
		  version.
		* **version_type**: just the version type ID specified.
		* **uncaught**: a special case that returns stats on
		  all requests that were unable to be routed to any instance.
		  ``input_id`` is ignored.
		* **pacemaker**: a special case that returns stats on
		  pacemaker activity (if that activity passes through
		  a router). ``input_id`` is ignored.

		:arg str name: The name of the set to return.
		:arg int input_id: The ID to match the set.
		:arg callable callback: The callback to call with a dict of
			stats.
		:arg str listtype: One of 'node' or 'vt'. 'node' is currently
			not implemented.
		"""
		if listtype not in ['node', 'vt']:
			raise ValueError("List type must be either node or vt.")

		def script_result(result):
			# The result is a list, so convert it to a dict.
			# The entries are in order, so we can just merge the
			# two together.
			stats = dict(zip(self.METRICS, result))
			callback(stats)

		real_list_type = 'stat_vt'
		if listtype == 'node':
			real_list_type = 'stat_node'

		# Call the redis script to generate the stats.
		self.redis.evalsha(
			self.configuration.redis_scripts['stats_standard.lua'],
			keys=[],
			args=[real_list_type, name, input_id],
			callback=script_result
		)

	def total_for_uncaught(self, callback, error_callback):
		"""
		Helper to return a list of stats for uncaught requests.
		"""
		self.stats_for_name('uncaught', None, callback)

	def total_for_pacemaker(self, callback, error_callback):
		"""
		Helper to return a list of stats for pacemaker requests.
		"""
		self.stats_for_name('pacemaker', None, callback)

	def history_for_name(self, name, input_id, metrics, callback, start, end=None, listtype='vt'):
		"""
		Fetch the router history for the given input name and ID.

		Name is one of a few options of aggregated sets
		to return. ``input_id`` then selects the specific
		aggregation.

		Name can be one of the following:

		* **workspace**: all the version type IDs in the
		  specified workspace.
		* **application**: all the version type IDs in the
		  specified application.
		* **version**: all the version type IDs in the specified
		  version.
		* **version_type**: just the version type ID specified.
		* **uncaught**: a special case that returns stats on
		  all requests that were unable to be routed to any instance.
		  ``input_id`` is ignored.
		* **pacemaker**: a special case that returns stats on
		  pacemaker activity (if that activity passes through
		  a router). ``input_id`` is ignored.

		Additionally:

		* This can return up to one value per second in the range;
		  keep your ranges as small as you need them.
		* ``start`` and ``end`` are unix timestamps, in UTC.

		The output looks as follows:

		.. code-block:: json

			{
				"metric": [
					[time, value],
					[time, value],
					...
				]
			}

		:arg str name: The name of the set to return.
		:arg int input_id: The ID to match the set.
		:arg list metrics: The metric graphs to return.
		:arg int start: The unix timestamp to start.
		:arg callable callback: The callback to call with a dict of
			stats.
		:arg int|None end: The unix timestamp to end.
		:arg str listtype: One of 'node' or 'vt'. 'node' is currently
			not implemented.
		"""
		if listtype not in ['node', 'vt']:
			raise ValueError("List type must be either node or vt.")

		if not end:
			end = int(time.time())

		# Make sure it's an int.
		start = int(start)

		if isinstance(metrics, basestring):
			metrics = [metrics]

		def script_result(result):
			# The result is a JSON encoded string, so decode it,
			# and then perform some postprocessing on it.
			decoded = json.loads(result)
			# At the top level, convert the dicts into a list.
			for key, entries in decoded.iteritems():
				result = []
				for timestamp, value in entries.iteritems():
					result.append([int(timestamp), value])

				# Sort the result.
				result.sort(key=lambda x: x[0])

				# And replace it in the resulting list.
				decoded[key] = result

			callback(decoded)

		real_list_type = 'history_vt'
		if listtype == 'node':
			real_list_type = 'history_node'

		# Call the redis script to generate the history.
		# Crude way to get a list of metrics in: JSON encode it.
		self.redis.evalsha(
			self.configuration.redis_scripts['stats_history.lua'],
			keys=[],
			args=[real_list_type, name, input_id, json.dumps(metrics), start, end],
			callback=script_result
		)
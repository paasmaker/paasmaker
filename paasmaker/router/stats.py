
import os
import json
import logging
import time

import paasmaker

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
		return "position_%s" % self.configuration.get_node_uuid()

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
		elif position == size:
			# Nothing's changed. No need to read the file at all.
			self.reading = False
			self.callback("No new log entries.")
		else:
			logger.debug("Starting to read %s from position %d.", filename, position)
			self.fp = open(filename, 'r')
			if position > 0:
				self.fp.seek(position)
			self._read_batch()

	def _read_batch(self):
		# Read in a batch.
		batch = self.fp.readlines(READ_SIZE_BATCH)
		logger.debug("%d lines in this batch.", len(batch))
		if len(batch) == 0:
			# Completed reading.
			self._finalize_batch()
		else:
			# Process this batch.
			self._process_batch(batch)

	def _process_batch(self, lines):
		# Parse them all.
		for line in lines:
			try:
				parsed = json.loads(line)
				key = parsed['key']
				if key == '':
					# Bad key. Just reset it.
					key = 'null'

				# Basic stats.
				self._store_value(key, 'requests', 1)
				self._store_value(key, 'bytes', parsed['bytes'])

				# The upstream response time, if given.
				if parsed['upstream_response_time'] != '-':
					# Convert it into decimal milliseconds.
					upstream_response_milliseconds = int(float(parsed['upstream_response_time']) * 1000)
					self._store_value(key, 'time', upstream_response_milliseconds)
					self._store_value(key, 'timecount', 1)

				# nginx's own time, converted into decimal milliseconds.
				nginx_time_milliseconds = int(float(parsed['nginx_response_time']) * 1000)
				self._store_value(key, 'nginxtime', nginx_time_milliseconds)

				# Split the response code into categories.
				code_category = "%dxx" % (parsed['code'] / 100)
				self._store_value(key, code_category, 1)

				# But why not, let's store the exact code too! It's quite cheap.
				self._store_value(key, parsed['code'], 1)

				# For graphs. The target keys are like this:
				# history_<vtid>_NNNNNNNNN_requests
				# Where NNNNNNN is the unix time in seconds at the top of the hour.
				# The key type is a hash.
				hour_top = parsed['timemsec'] - (parsed['timemsec'] % 3600)
				history_prefix = "history_%s_%d" % (key, hour_top)
				# And co-orce this one into an int.
				history_key = "%d" % parsed['timemsec']

				# Basic stats.
				self._store_hash_value("%s_requests" % history_prefix, history_key, 1)
				self._store_hash_value("%s_bytes" % history_prefix, history_key, parsed['bytes'])

				# Upstream response time and count.
				if parsed['upstream_response_time'] != '-':
					# Convert it into decimal milliseconds.
					self._store_hash_value("%s_time" % history_prefix, history_key, upstream_response_milliseconds)
					self._store_hash_value("%s_timecount" % history_prefix, history_key, 1)

				# Response code.
				self._store_hash_value("%s_%s" % (history_prefix, code_category), history_key, 1)

				# nginx's own time, converted into decimal milliseconds.
				self._store_hash_value("%s_nginxtime" % history_prefix, history_key, nginx_time_milliseconds)

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
		final_key = "stat_%s_%s" % (key, metric)
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
	METRICS = [
		'bytes',
		'1xx',
		'2xx',
		'3xx',
		'4xx',
		'5xx',
		'requests',
		'time',
		'timecount',
		'nginxtime'
	]
	AVERAGES = [
		('time', 'timecount'),
		('nginxtime', 'requests')
	]
	PERCENTAGES = [
		('1xx', 'requests'),
		('2xx', 'requests'),
		('3xx', 'requests'),
		('4xx', 'requests'),
		('5xx', 'requests')
	]

	DISPLAY_SET = [
		# TODO: According to the docs, should be able to use %n to format
		# including thousands seperators... but this doesn't work.
		{
			'title': 'Requests',
			'key': 'requests',
			'format': '%d',
			'primary': True
		},
		{
			'title': 'Bytes',
			'key': 'bytes',
			'format': '%d',
			'primary': True
		},
		{
			'title': 'Average Time',
			'key': 'time_average',
			'format': '%d',
			'primary': True
		},
		{
			'title': '1xx',
			'key': '1xx',
			'format': '%d',
			'primary': False
		},
		{
			'title': '1xx Percentage',
			'key': '1xx_percentage',
			'format': '%0.2f%%',
			'primary': False
		},
		{
			'title': '2xx',
			'key': '2xx',
			'format': '%d',
			'primary': False
		},
		{
			'title': '2xx Percentage',
			'key': '2xx_percentage',
			'format': '%0.2f%%',
			'primary': False
		},
		{
			'title': '3xx',
			'key': '3xx',
			'format': '%d',
			'primary': False
		},
		{
			'title': '3xx Percentage',
			'key': '3xx_percentage',
			'format': '%0.2f%%',
			'primary': False
		},
		{
			'title': '4xx',
			'key': '4xx',
			'format': '%d',
			'primary': False
		},
		{
			'title': '4xx Percentage',
			'key': '4xx_percentage',
			'format': '%0.2f%%',
			'primary': False
		},
		{
			'title': '5xx',
			'key': '5xx',
			'format': '%d',
			'primary': False
		},
		{
			'title': '5xx Percentage',
			'key': '5xx_percentage',
			'format': '%0.2f%%',
			'primary': False
		},
		{
			'title': 'NGINX Time',
			'key': 'nginxtime_average',
			'format': '%d',
			'primary': False
		}
	]

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

	def vtset_for_name(self, name, input_id, callback):
		"""
		Fetch a version type ID list for the given
		input. This returns a list with the named aggregation.

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
		* **node**: all the version type IDs for instances on
		  the given node ID.
		* **version_type**: just the version type ID specified.
		* **uncaught**: a special case that returns stats on
		  all requests that were unable to be routed to any instance.
		  ``input_id`` is ignored.
		* **pacemaker**: a special case that returns stats on
		  pacemaker activity (if that activity passes through
		  a router). ``input_id`` is ignored.

		:arg str name: The name of the set to return.
		:arg int input_id: The ID to match the set.
		:arg callable callback: The callback to call with the list
			of version type IDs.
		"""
		def got_set(vtids):
			callback(list(vtids))

		if name == 'workspace' or name == 'application' or \
			name == 'version' or name == 'node':
			# These are valid.
			pass
		elif name == 'version_type':
			# Pass it back directly.
			callback([input_id])
			return
		elif name == 'uncaught':
			# Pass back a suitable list.
			callback(['null'])
			return
		elif name == 'pacemaker':
			callback(['pacemaker'])
			return
		else:
			raise ValueError("Unknown input name %s" % name)

		set_key = "%s_%d_vtids" % (name, input_id)
		self.redis.smembers(set_key, callback=got_set)

	def total_for_uncaught(self, callback, error_callback):
		"""
		Helper to return a list of stats for uncaught requests.
		"""
		self.total_for_list(['null'], callback, error_callback)

	def total_for_pacemaker(self, callback, error_callback):
		"""
		Helper to return a list of stats for pacemaker requests.
		"""
		self.total_for_list(['pacemaker'], callback, error_callback)

	def total_for_list(self, idset, callback, error_callback):
		"""
		Return the stats for the given version type ID list set.

		A dict with all the possible stats is returned, which is
		an aggregate of all the version type IDs supplied.

		If an empty list of IDs is supplied, the error callback is
		called.

		:arg list idset: A list of version type IDs to fetch
			the stats for.
		:arg callable callback: A callback to call with the stats.
			Passed a single argument which is a dict of stats.
		:arg callable error_callback: A callback used if an error
			occurs.
		"""
		def on_stats_fetched(stats):
			# Parse the result from Redis into something more manageable.
			metric_totals = {}
			# Reverse it, so we can pop entries off it.
			stats.reverse()
			for vtid in idset:
				for metric in self.METRICS:
					stat = stats.pop()
					if stat == None:
						# Didn't exist in redis. So start it at zero.
						stat = 0
					if not metric_totals.has_key(metric):
						metric_totals[metric] = 0
					metric_totals[metric] += int(stat)

			# Now hand it off to something else to finalize it.
			self._finalize_stats(metric_totals, callback)

		if len(idset) == 0:
			# No sets to process - which will cause an error
			# later. Call the error callback.
			error_callback("Empty ID list supplied.")
		else:
			# Ok, now, for the given id set list,
			# query out all the relevant metrics.
			pipeline = self.redis.pipeline(True)
			for vtid in idset:
				for metric in self.METRICS:
					pipeline.get("stat_%s_%s" % (vtid, metric))
			pipeline.execute(callback=on_stats_fetched)

	def _finalize_stats(self, totals, callback):
		# Calculate any averages and percentages.
		for average in self.AVERAGES:
			output_key = "%s_average" % average[0]
			quotient = totals[average[0]]
			divisor = totals[average[1]]

			if divisor == 0:
				totals[output_key] = 0
			else:
				totals[output_key] = float(quotient) / float(divisor)

		for percentage in self.PERCENTAGES:
			output_key = "%s_percentage" % percentage[0]

			quotient = totals[percentage[0]]
			divisor = totals[percentage[1]]

			if divisor == 0:
				totals[output_key] = 0
			else:
				totals[output_key] = (float(quotient) / float(divisor)) * 100.0

		# And we're done.
		callback(totals)

	def history_for_list(self, idset, metric, callback, error_callback, start, end=None):
		"""
		Return the history for a given metric and version type ID set,
		in the given time frame.

		* This can return up to one value per second in the range;
		  keep your ranges as small as you need them.
		* ``start`` and ``end`` are unix timestamps, in UTC.
		* The output looks as follows::

			[
				[time, value],
				[time, value],
				...
			]

		:arg list idset: The list of version type IDs to aggregate.
		:arg str metric: One of the metrics for which the system records
			history.
		:arg callable callback: The callback to call with the history. This
			is called with a single argument which is a list. Each list element
			contains another list, in the format ``[time, value]``.
		"""
		# CAUTION: Returns up to 1 value per second in the given range.
		# Use very carefully!
		# 1. Build list of history sets required from redis.
		# 2. Query all those history sets.
		# 3. Merge all those history sets together, culling off data in the process.
		# 4. Perform finalization of the data (averaging, etc)

		if not end:
			end = int(time.time())

		# Make sure it's an int.
		start = int(start)

		def on_stats_fetched(stats):
			# Parse the result from Redis into something more manageable.
			intermediate_merge = {}
			for stat_set in stats:
				for key, value in stat_set.iteritems():
					ikey = int(key)
					if ikey >= start and ikey <= end:
						# The key here is the unix timestamp of the data.
						if not intermediate_merge.has_key(key):
							intermediate_merge[key] = 0

						intermediate_merge[key] += int(value)

			# Now, convert that hash map into a sorted list.
			ordered_data = []
			for key, value in intermediate_merge.iteritems():
				ordered_data.append([int(key), value])

			ordered_data.sort(key=lambda x: x[0])

			# TODO: Handle averaging...
			callback(ordered_data)
			# end of on_stats_fetched()

		# Output:
		# [
		#   [time, value]
		# ]
		# Queries from redis:
		# history_<vtid>_NNNNNNNNNN_<metric> x 1 per vtid x 1 per hour boundary.
		real_start = int(start - (start % 3600))
		hour_boundaries = range(real_start, int(end), 3600)

		pipeline = self.redis.pipeline(True)
		for vtid in idset:
			for boundary in hour_boundaries:
				key = "history_%s_%s_%s" % (
					vtid,
					boundary,
					metric
				)
				pipeline.hgetall(key)

		pipeline.execute(on_stats_fetched)
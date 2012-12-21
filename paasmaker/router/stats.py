
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
	def __init__(self, configuration):
		self.configuration = configuration
		self.reading = False
		self.records = {}
		self.hashrecords = {}

	def get_position_key(self):
		return "position_%s" % self.configuration.get_node_uuid()

	def read(self, callback, error_callback):
		if self.reading:
			# Already reading, so don't start reading again.
			callback("Still reading.")
			return
		else:
			self.reading = True
			self.records = {}
			self.hashrecords = {}

		# Fetch the stats redis instance.
		self.callback = callback
		self.error_callback = error_callback
		self.configuration.get_stats_redis(self._got_redis, error_callback)

	def _got_redis(self, redis):
		# First query the last position we were up to.
		self.redis = redis
		self.redis.get(self.get_position_key(), self._got_position)

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
		final_key = "stat_%s_%s" % (key, metric)
		if self.records.has_key(final_key):
			self.records[final_key] += value
		else:
			self.records[final_key] = value

	def _store_hash_value(self, bucket, key, value):
		if not self.hashrecords.has_key(bucket):
			self.hashrecords[bucket] = {}
		if not self.hashrecords[bucket].has_key(key):
			self.hashrecords[bucket][key] = 0

		self.hashrecords[bucket][key] += value

	def _finalize_batch(self):
		position = self.fp.tell()
		logger.debug("Completed reading up to position %d", position)
		logger.debug("Recording %d stats.", len(self.records))
		pipeline = self.redis.pipeline(True)
		for key, value in self.records.iteritems():
			pipeline.incrby(key, value)
		for bucket, keyset in self.hashrecords.iteritems():
			for key, value in keyset.iteritems():
				pipeline.hincrby(bucket, key, amount=value)
		pipeline.set(self.get_position_key(), position)
		pipeline.execute(self._batch_finalized)

	def _batch_finalized(self, result):
		logger.info("Completed writing stats to redis.")
		self.fp.close()
		self.reading = False
		self.callback("Completed reading file.")

class StatsLogPeriodicManager(object):
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
		self.periodic.start()

	def read_stats(self):
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
		self.ready_callback = callback
		self.configuration.get_stats_redis(
			self._redis_ready,
			error_callback
		)

	def _redis_ready(self, redis):
		self.redis = redis
		self.ready_callback()

	def vtset_for_name(self, name, input_id, callback):
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
		self.total_for_list(['null'], callback, error_callback)

	def total_for_pacemaker(self, callback, error_callback):
		self.total_for_list(['pacemaker'], callback, error_callback)

	def total_for_list(self, idset, callback, error_callback):
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
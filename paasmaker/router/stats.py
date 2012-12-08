
import os
import json
import logging

import paasmaker

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READ_SIZE_BATCH = 8192 # Read this many bytes/lines in one go.

class StatsLogReader(object):
	def __init__(self, configuration):
		self.configuration = configuration
		self.reading = False
		self.records = {}

	def get_position_key(self):
		return "position_%s" % self.configuration.get_node_uuid()

	def read(self, callback, error_callback):
		if self.reading:
			# Already reading, so don't start reading again.
			callback("Still reading.")
		else:
			self.reading = True
			self.records = {}

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

				# Basic stats.
				self._store_value(key, 'requests', 1)
				self._store_value(key, 'bytes', parsed['bytes'])

				# The upstream response time, if given.
				if parsed['upstream_response_time'] != '-':
					# Convert it into decimal milliseconds.
					self._store_value(key, 'time', int(float(parsed['upstream_response_time']) * 1000))
					self._store_value(key, 'timecount', 1)

				# nginx's own time, converted into decimal milliseconds.
				self._store_value(key, 'nginxtime', int(float(parsed['nginx_response_time']) * 1000))

				# Split the response code into categories.
				code_category = "%dxx" % (parsed['code'] / 100)
				self._store_value(key, code_category, 1)

				# But why not, let's store the exact code too! It's quite cheap.
				self._store_value(key, parsed['code'], 1)

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

	def _finalize_batch(self):
		position = self.fp.tell()
		logger.debug("Completed reading up to position %d", position)
		logger.debug("Recording %d stats.", len(self.records))
		pipeline = self.redis.pipeline(True)
		for key, value in self.records.iteritems():
			pipeline.incrby(key, value)
		pipeline.set(self.get_position_key(), position)
		pipeline.execute(self._batch_finalized)

	def _batch_finalized(self, result):
		logger.info("Completed writing stats to redis.")
		self.fp.close()
		self.reading = False
		self.callback("Completed reading file.")

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

	def __init__(self, configuration, callback, error_callback):
		self.configuration = configuration
		self.callback = callback
		self.error_callback = error_callback

	def for_version_type(self, version_type_id):
		# Jump directly to the list.
		self._for_set_name([version_type_id])

	def for_version(self, version_id):
		self._for_set_name('version_%s_vtids' % version_id)

	def for_application(self, application_id):
		self._for_set_name('application_%s_vtids' % application_id)

	def for_workspace(self, workspace_id):
		self._for_set_name('workspace_%s_vtids' % workspace_id)

	def _for_set_name(self, set_name):
		def on_redis(redis):
			# Fetch the set name.
			if isinstance(set_name, list):
				# Use the list directly.
				self._for_list(set_name, redis)
			else:
				# Ask redis for that set of IDs, and then process that.
				def on_set_list(set_list):
					if not set_list:
						self.error_callback('No such list for %s' % set_name)
					else:
						self._for_list(set_list, redis)

				redis.smembers(set_name, callback=on_set_list)

		self.configuration.get_stats_redis(on_redis, self.error_callback)

	def _for_list(self, idset, redis):
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
			self._finalize_stats(metric_totals)

		# Ok, now, for the given id set list,
		# query out all the relevant metrics.
		pipeline = redis.pipeline(True)
		for vtid in idset:
			for metric in self.METRICS:
				pipeline.get("stat_%s_%s" % (vtid, metric))
		pipeline.execute(callback=on_stats_fetched)

	def _finalize_stats(self, totals):
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
		self.callback(totals)
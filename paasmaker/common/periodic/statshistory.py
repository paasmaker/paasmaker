#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import time
import gzip
import json
import shutil
import os

import paasmaker
from base import BasePeriodic, BasePeriodicTest

import colander

class StatsHistoryConfigurationSchema(colander.MappingSchema):
	max_age = colander.SchemaNode(colander.Integer(),
		title="Maximum stats age",
		description="Maximum age for graph stats. After this time, they are written to disk and removed from Redis.",
		default=3600 * 6,
		missing=3600 * 6)

class StatsHistoryCleaner(BasePeriodic):
	"""
	A plugin to remove old history stats from Redis, to free up memory.
	"""

	OPTIONS_SCHEMA = StatsHistoryConfigurationSchema()
	API_VERSION = "0.9.0"

	def on_interval(self, callback, error_callback):
		if not self.configuration.is_pacemaker():
			callback("Not a pacemaker, so not writing out stats.")
			return

		self.callback = callback
		self.error_callback = error_callback
		self.clean_hours = 0

		self.configuration.get_stats_redis(self._got_redis, error_callback)

	def _got_redis(self, redis):
		self.redis = redis

		# List all history stats.
		self.redis.keys('history*', self._got_keys)

	def _got_keys(self, history_keys):
		# Sort them so they group correctly.
		history_keys.sort()

		# Now split them into groups now. The group is based
		# on the timestamp. The keys look like this:
		# history_<type>:<id>:<timestamp>:<metric>
		groups = []
		since = time.time() - self.options['max_age']

		group_accumulator = []
		last_timestamp = None
		for i in range(len(history_keys)):
			this_key = history_keys[i]
			timestamp = int(this_key.split(':')[2])

			# Check to see if this is in the range.
			if timestamp > since:
				# Skip this one.
				continue

			if timestamp != last_timestamp:
				# End of group.
				if len(group_accumulator) > 0:
					groups.append(group_accumulator)
					group_accumulator = []

			group_accumulator.append(this_key)
			last_timestamp = timestamp

		self.groups = groups

		self.logger.info("Found %d stats groups to archive.", len(self.groups))

		# Start processing the groups.
		self._process_group()

	def _process_group(self):
		try:
			group = self.groups.pop()

			self.logger.info("Starting to prcess group starting with %s...", group[0])

			def deleted_all(result):
				self.logger.info("Group deleted. Moving onto next group.")
				# Done, move onto the next set.
				self.configuration.io_loop.add_callback(self._process_group)

			def fetched_all(results):
				self.logger.info("Fetched group, compressing and writing to disk.")
				# Match the results with their group.
				complete_output = {}
				merged = dict(zip(group, results))

				# Write it out to disk.
				# Don't write it to disk if the file already exists;
				# this prevents issues where old stats came in really
				# late after it had already been written. There isn't
				# a nice way to handle this at the moment. TODO: Revise.
				title = ".".join(group[0].split(':')[0:3])
				path = self.configuration.get_scratch_path_exists('old-history')
				full_path = os.path.join(path, title + '.json.gz')
				if not os.path.exists(full_path):
					fp = gzip.GzipFile(full_path, 'w')
					fp.write(json.dumps(merged))
					fp.close()

				# Now delete it from Redis.
				pipeline = self.redis.pipeline()
				for entry in group:
					pipeline.delete(entry)
				pipeline.execute(deleted_all)

			pipeline = self.redis.pipeline()
			for entry in group:
				pipeline.hgetall(entry)
			pipeline.execute(fetched_all)

		except IndexError, ex:
			# No more to process.
			self.callback("Completed exporting stats.")

class StatsHistoryCleanerTest(BasePeriodicTest):
	def setUp(self):
		super(StatsHistoryCleanerTest, self).setUp()

		# TODO: This is tested by using another Redis database
		# that already has data in it. Update this unit test to better
		# represent this.
		# redis_path = self.configuration.get_scratch_path_exists('redis', 'stats')
		# target = os.path.join(redis_path, 'dump.rdb')
		# source = '/home/daniel/dev/paasmaker/dump.rdb'
		# shutil.copyfile(source, target)

		self.configuration.plugins.register(
			'paasmaker.periodic.statshistory',
			'paasmaker.common.periodic.statshistory.StatsHistoryCleaner',
			{},
			'Stats History Cleanup Plugin'
		)

		self.configuration.startup_job_manager(self.stop, self.stop)
		self.wait()

	def test_simple(self):
		# Do a cleanup. This job should not be removed.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.statshistory',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn("Completed exporting stats", self.message, "Incorrect message.")

import os
import glob
import uuid
import time
import logging

import paasmaker
from base import BasePeriodic, BasePeriodicTest

import colander

class LogsCleanerConfigurationSchema(colander.MappingSchema):
	max_age = colander.SchemaNode(colander.Integer(),
		title="Maximum log age",
		description="Maximum age for a log file. After this age, it is deleted. In seconds. Default 7 days.",
		default=86400 * 7,
		missing=86400 * 7)

class LogsCleaner(BasePeriodic):
	"""
	A plugin to remove log files once they reach a certain age.
	"""
	OPTIONS_SCHEMA = LogsCleanerConfigurationSchema()
	API_VERSION = "0.9.0"

	def on_interval(self, callback, error_callback):
		# Start by making a list of directories at the top level.
		self.paths = glob.glob(os.path.join(self.configuration.get_flat('log_directory'), '*'))

		# Process them one by one.
		self.callback = callback
		self.error_callback = error_callback
		self.removed_files = 0

		self.older_than = int(time.time()) - self.options['max_age']

		self.logger.info("Starting cleanup process.")
		self._fetch_directory()

	def _fetch_directory(self):
		try:
			this_dir = self.paths.pop()

			self._process_directory(this_dir)
		except IndexError, ex:
			# No more to process.
			self.logger.info("Completed cleanup process. Removed %d log files.", self.removed_files)
			self.callback("Removed %d log files." % self.removed_files)

	def _process_directory(self, path):
		self.directory_contents = glob.glob(
			os.path.join(path, '*.log')
		)

		self._fetch_file()

	def _fetch_file(self):
		try:
			this_file = self.directory_contents.pop()

			information = os.stat(this_file)

			if information.st_mtime < self.older_than:
				# This file should be removed.

				# Check the file size. If it's over a 1MB
				# delete it using a subprocess and rm. Why?
				# Because unlink() will block, and on large
				# log files and certain filesystems, this
				# could hang up the process for a while.
				if information.st_size > 1024 * 1024:
					self.logger.error("Removing %s via subprocess", this_file)
					def on_rm_finished(code):
						# Move onto the next file.
						self.removed_files += 1
						self.configuration.io_loop.add_callback(self._fetch_file)

					# TODO: This won't work on Windows.
					process = paasmaker.util.popen.Popen(
						['rm', this_file],
						io_loop=self.configuration.io_loop,
						on_exit=on_rm_finished
					)
				else:
					self.logger.error("Removing %s", this_file)
					os.unlink(this_file)
					self.removed_files += 1
					# Process the next file on the IO loop.
					self.configuration.io_loop.add_callback(self._fetch_file)
			else:
				# Nope. Move on.
				self.configuration.io_loop.add_callback(self._fetch_file)

		except IndexError, ex:
			# No more to process.
			self.configuration.io_loop.add_callback(self._fetch_directory)

	def _handle_file(self, file):
		self.configuration.io_loop.add_callback(self._fetch_file)

class LogsCleanerTest(BasePeriodicTest):
	def setUp(self):
		super(LogsCleanerTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.periodic.logs',
			'paasmaker.common.periodic.logs.LogsCleaner',
			{},
			'Log Cleanup Plugin'
		)

		self.logger = logging.getLogger('job')
		# Prevent propagation to the parent. This prevents extra messages
		# during unit tests.
		self.logger.propagate = False
		# Clean out all handlers. Otherwise multiple tests fail.
		self.logger.handlers = []

		paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(self.configuration)

	def test_simple(self):
		# Create a few sample log files.
		for i in range(10):
			job_id = str(uuid.uuid4())
			job_logger = self.configuration.get_job_logger(job_id)
			job_logger.error("Test")
			job_logger.finished()

		# Make one big log file.
		job_id = str(uuid.uuid4())
		job_logger = self.configuration.get_job_logger(job_id)
		test_string = "test" * 1024
		for i in range(1024):
			job_logger.error(test_string)
		job_logger.finished()

		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.logs',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		# This should remove nothing.
		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 0 ", self.message, "Wrong message returned.")

		# Adjust all the log files so that they are older than the threshold.
		expected_age = time.time() - (86400 * 8)
		for log_file in glob.glob(os.path.join(self.configuration.get_flat('log_directory'), '*', '*.log')):
			os.utime(log_file, (expected_age, expected_age))

		# Now clean.
		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 11 ", self.message, "Wrong message returned.")
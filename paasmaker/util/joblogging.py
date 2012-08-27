#!/usr/bin/env python

import unittest
import logging
import warnings
import os
import paasmaker
import shutil

class JobLoggingHandler(logging.Handler):
	def __init__(self, configuration):
		self.configuration = configuration
		self.handlers = {}
		logging.Handler.__init__(self)
		# Create the log destination.
		try:
			os.makedirs(configuration.get_global('log_directory'))
		except OSError, ex:
			# Probably already existed. TODO: Detect if this was a failure.
			logging.warning('Failed to create log directory: %s', str(ex))
		self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

	def emit(self, record):
		# TODO: Close off old loggers for memory purposes.
		# This handler only logs if there is a job id.
		if record.job:
			job_id = record.job
			# Find a handler.
			handler = self.get_handler(job_id)
			handler.emit(record)

	def get_path(self, job_id):
		path = os.path.join(self.configuration.get_global('log_directory'), job_id + '.log')
		return path

	def get_handler(self, job_id):
		if self.handlers.has_key(job_id):
			return self.handlers[job_id]
		else:
			handler = logging.FileHandler(self.get_path(job_id))
			handler.setFormatter(self.formatter)
			self.handlers[job_id] = handler
			return handler

class JobLoggingTest(unittest.TestCase):
	minimum_config = """
auth_token = 'supersecret'
"""

	def setUp(self):
		# TODO: Refactor this test.
		warnings.simplefilter("ignore")
		self.tempnam = os.tempnam()
		open(self.tempnam, 'w').write(self.minimum_config)

		self.configuration = paasmaker.configuration.Configuration()
		self.logger = logging.getLogger('job')

		# TODO: Refactor this.
		self.logger.setLevel(logging.DEBUG)

		self.handler = JobLoggingHandler(self.configuration)
		self.logger.addHandler(self.handler)		

	def tearDown(self):
		if os.path.exists(self.tempnam):
			os.unlink(self.tempnam)
		# TODO: This can be dangerous!
		shutil.rmtree(self.configuration.get_global('log_directory'))

	def test_log_jobs(self):
		# Log, then check it exists in the log file.
		self.logger.debug('Test', extra={'job':"1"})
		self.logger.debug('Test 2', extra={'job':"2"})
		job1path = self.handler.get_path("1")
		job2path = self.handler.get_path("2")
		self.assertTrue(os.path.exists(job1path), "Log file for job 1 does not exist.")
		self.assertTrue(os.path.exists(job2path), "Log file for job 2 does not exist.")

if __name__ == '__main__':
	unittest.main()

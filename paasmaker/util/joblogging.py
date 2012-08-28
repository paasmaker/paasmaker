#!/usr/bin/env python

import unittest
import logging
import paasmaker
import os

class JobLoggingHandler(logging.Handler):
	def __init__(self, configuration):
		self.configuration = configuration
		self.handlers = {}
		logging.Handler.__init__(self)
		self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

	def emit(self, record):
		# This handler only logs if there is a job id.
		if record.__dict__.has_key('job'):
			job_id = record.job
			# Find a handler.
			handler = self.get_handler(job_id)
			handler.emit(record)
			# If it's complete, destroy that handler.
			if record.__dict__.has_key('complete') and record.complete:
				self.close_handler(job_id)

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

	def close_handler(self, job_id):
		if self.handlers.has_key(job_id):
			del self.handlers[job_id]

	@staticmethod
	def setup_joblogger(configuration):
		joblogger = logging.getLogger('job')
		# TODO: This level should be adjustable, but how to make it
		# adjustable per job?
		joblogger.setLevel(logging.DEBUG)
		joblogger.addHandler(JobLoggingHandler(configuration))

class JobLoggingTest(unittest.TestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub()
		self.logger = logging.getLogger('job')
		# Clean out all handlers. Otherwise multiple tests fail.
		self.logger.handlers = []

		JobLoggingHandler.setup_joblogger(self.configuration)

		# Hack to fetch the handler.
		self.handler = self.logger.handlers[0]

	def tearDown(self):
		self.configuration.cleanup()

	def test_log_jobs(self):
		# Log, then check it exists in the log file.
		self.logger.debug('Test 1', extra={'job':"1"})
		self.logger.debug('Test 2', extra={'job':"2"})
		job1path = self.handler.get_path("1")
		job2path = self.handler.get_path("2")
		self.assertTrue(os.path.exists(job1path), "Log file for job 1 does not exist.")
		self.assertTrue(os.path.exists(job2path), "Log file for job 2 does not exist.")
		log1content = open(job1path, 'r').read()
		log2content = open(job2path, 'r').read()
		self.assertEquals(len(open(job1path, 'r').read().split('\n')), 2)
		self.assertEquals(len(open(job2path, 'r').read().split('\n')), 2)
		self.assertIn('Test 1', log1content)
		self.assertIn('Test 2', log2content)

	def test_log_jobs_without_jobid(self):
		# Log to the appropriate logger without the right parameters.
		# It shouldn't die with an error...
		self.logger.debug('Test')

	def test_complete_job(self):
		# Mark a job as completed.
		self.logger.debug('Test', extra={'job':"1", 'complete':True})
		self.assertEquals(len(self.handler.handlers.keys()), 0)

if __name__ == '__main__':
	unittest.main()

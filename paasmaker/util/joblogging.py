import unittest
import logging
import paasmaker
import os
import uuid
import json

from pubsub import pub

JOB_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class JobLoggingFileHandler(logging.Handler):
	def __init__(self, configuration):
		self.configuration = configuration
		self.handlers = {}
		logging.Handler.__init__(self)
		self.formatter = logging.Formatter(JOB_LOG_FORMAT)

		pub.subscribe(self.job_status_change, 'job.status')

	def emit(self, record):
		# This handler only logs if there is a job id.
		if record.__dict__.has_key('job'):
			job_id = record.job
			# Find a handler, and get that one to emit the record.
			handler = self.get_handler(job_id)
			handler.emit(record)

	def get_handler(self, job_id):
		if self.handlers.has_key(job_id):
			return self.handlers[job_id]
		else:
			handler = logging.FileHandler(self.configuration.get_job_log_path(job_id))
			handler.setFormatter(self.formatter)
			self.handlers[job_id] = handler
			return handler

	def close_handler(self, job_id):
		if self.handlers.has_key(job_id):
			self.handlers[job_id].close()
			del self.handlers[job_id]

	def job_status_change(self, job_id, state, source):
		if state in paasmaker.common.core.constants.JOB_FINISHED_STATES:
			# Pubsub callback for job status change.
			# Close off that handler.
			self.close_handler(job_id)

class JobLoggerAdapter(logging.LoggerAdapter):
	def __init__(self, logger, job_id, configuration):
		self.job_id = job_id
		self.configuration = configuration
		super(JobLoggerAdapter, self).__init__(logger, {'job':job_id})

	def complete(self, state, summary):
		# Dump out some JSON to the log file.
		flat_summary = {'state': state, 'summary': summary}
		self.info(json.dumps(flat_summary))
		# Publish to the audit queue.
		self.configuration.send_job_complete(self.job_id, state, summary)
		# And to the state queue.
		self.configuration.send_job_status(self.job_id, state, summary)

	@staticmethod
	def setup_joblogger(configuration):
		joblogger = logging.getLogger('job')
		# TODO: This level should be adjustable, but how to make it
		# adjustable per job?
		joblogger.setLevel(logging.DEBUG)
		joblogger.addHandler(JobLoggingFileHandler(configuration))

class JobLoggingTest(unittest.TestCase):
	def setUp(self):
		self.configuration = paasmaker.common.configuration.ConfigurationStub()
		self.logger = logging.getLogger('job')
		# Prevent propagation to the parent. This prevents extra messages
		# during unit tests.
		self.logger.propagate = False
		# Clean out all handlers. Otherwise multiple tests fail.
		self.logger.handlers = []

		JobLoggerAdapter.setup_joblogger(self.configuration)

		# Hack to fetch the handler.
		self.handler = self.logger.handlers[0]

	def tearDown(self):
		self.configuration.cleanup()

	def test_log_jobs(self):
		# Log, then check it exists in the log file.
		id1 = str(uuid.uuid4())
		id2 = str(uuid.uuid4())

		job1logger = self.configuration.get_job_logger(id1)
		job1logger.debug('Test 1')

		job2logger = self.configuration.get_job_logger(id2)
		job2logger.debug('Test 2')

		job1path = self.configuration.get_job_log_path(id1)
		job2path = self.configuration.get_job_log_path(id2)

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
		id1 = str(uuid.uuid4())
		job1logger = self.configuration.get_job_logger(id1)
		job1logger.debug('Test')

		# Check that it has a handler.
		self.assertEquals(len(self.handler.handlers.keys()), 1, "A handler was expected.")

		# Send a job update (that's not a finished status) and make sure the handler is still open.
		self.configuration.send_job_status(id1, 'RUNNING')
		self.assertEquals(len(self.handler.handlers.keys()), 1, "A handler was expected.")

		# Mark a job as completed.
		job1logger.complete('FINISHED', "Success")
		self.assertEquals(len(self.handler.handlers.keys()), 0, "Handler was not closed and freed.")

		# Now check that the summary was written and parseable.
		# TODO: Find nicer way to organise these.
		job1path = self.configuration.get_job_log_path(id1)
		contents = open(job1path, 'r').read()
		self.assertIn('state', contents)
		self.assertIn('FINISHED', contents)
		self.assertIn('{', contents)
		self.assertIn('}', contents)


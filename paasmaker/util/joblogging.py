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
			del self.handlers[job_id]

class JobLoggingPubHandler(logging.Handler):
	def __init__(self, configuration):
		self.configuration = configuration
		logging.Handler.__init__(self)
		self.setFormatter(logging.Formatter(JOB_LOG_FORMAT))

	def emit(self, record):
		# This handler only logs if there is a job id.
		if record.__dict__.has_key('job'):
			job_id = record.job
			job_topic = self.configuration.get_job_pub_topic(job_id)
			# Don't proceed any further if there is no one listening.
			# We're trying to avoid the self.format() call, as that can
			# be expensive.
			# TODO: this is a bit hacky.
			job_topic_key = ".".join(job_topic)
			if pub.topicsMap.has_key(job_topic_key) and len(pub.topicsMap[job_topic_key]._Topic__listeners) == 0:
				return
			# Render the message. Note we add a newline, because the file
			# handler also does this... so if we didn't, we'd be out by one-byte-per-entry.
			message = self.format(record) + "\n"
			# Publish the message to interested parties.
			pub.sendMessage(job_topic, message=message, job_id=job_id)
			# If it's complete, unsubscribe all.
			# And then publish a message to say that the job is complete.
			if record.__dict__.has_key('complete') and record.complete:
				pub.sendMessage(('job', 'complete'), job_id=job_id, summary=self.format(record))
				pub.delTopic(job_topic)

class JobLoggerAdapter(logging.LoggerAdapter):
	def __init__(self, logger, job_id, configuration):
		self.job_id = job_id
		self.configuration = configuration
		super(JobLoggerAdapter, self).__init__(logger, {'job':job_id})

	def complete(self, success, summary):
		# Job should now be complete...
		# This will trigger closing the file.
		flat_summary = {'success': success, 'summary': summary}
		self.logger.info(json.dumps(flat_summary), extra={'job':self.job_id, 'complete':True})

	@staticmethod
	def setup_joblogger(configuration):
		joblogger = logging.getLogger('job')
		# TODO: This level should be adjustable, but how to make it
		# adjustable per job?
		joblogger.setLevel(logging.DEBUG)
		joblogger.addHandler(JobLoggingFileHandler(configuration))
		joblogger.addHandler(JobLoggingPubHandler(configuration))

class JobLoggingTest(unittest.TestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub()
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
		# Mark a job as completed.
		id1 = str(uuid.uuid4())
		job1logger = self.configuration.get_job_logger(id1)
		job1logger.debug('Test')
		job1logger.complete(True, "Success")
		self.assertEquals(len(self.handler.handlers.keys()), 0, "Handler was not closed and freed.")

		# Now check that the summary was written and parseable.
		# TODO: Find nicer way to organise these.
		job1path = self.configuration.get_job_log_path(id1)
		contents = open(job1path, 'r').read()
		self.assertIn('Success', contents)
		self.assertIn('true', contents)
		self.assertIn('{', contents)
		self.assertIn('}', contents)


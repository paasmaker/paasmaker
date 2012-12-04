import unittest
import logging
import paasmaker
import os
import uuid
import json

import tornado.testing

from paasmaker.common.core import constants

from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

JOB_LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

class JobLoggingFileHandler(logging.Handler):
	def __init__(self, configuration):
		logger.debug("Setting up JobLoggingFileHandler.")
		self.configuration = configuration
		self.handlers = {}
		logging.Handler.__init__(self)
		self.formatter = logging.Formatter(JOB_LOG_FORMAT)

		# Subscribe to job updates, so we can close handlers as appropriate.
		pub.subscribe(self.job_status_change, 'job.status')
		# And a takeover if we want to free the FD's for another purpose.
		pub.subscribe(self.job_file_takeover, 'job.takeover')

		logger.debug("Completed __init__ of JobLoggingFileHandler.")

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

	def job_status_change(self, message):
		logger.debug("Job status change: job_id %s, state %s, source %s", message.job_id, message.state, message.source)
		if message.state in constants.JOB_FINISHED_STATES:
			# Pubsub callback for job status change.
			# Close off that handler.
			self.close_handler(message.job_id)

	def job_file_takeover(self, job_id):
		# Close the handler for that job - freeing up the file.
		self.close_handler(job_id)

# TODO: This doesn't seem like the best idea from the outset.
# However... inotify will notify us as soon as the file changes.
# And if there is a lot of log output, it would make sense to batch
# it up in 200ms batches. I'm open to suggestions here.
class JobWatcher(object):
	def __init__(self, configuration):
		self.configuration = configuration
		self.watches = {}
		# TODO: Allow this interval to be adjusted?
		self.periodic = tornado.ioloop.PeriodicCallback(self.check_log_files, 200, io_loop=configuration.io_loop)
		self.active = False

	def add_watch(self, job_id):
		if self.watches.has_key(job_id):
			self.watches[job_id]['ref'] += 1
			logger.debug("Incrementing reference count for %s - now %d.", job_id, self.watches[job_id]['ref'])
		else:
			filename = self.configuration.get_job_log_path(job_id)
			self.watches[job_id] = {'size': os.path.getsize(filename), 'filename': filename, 'ref': 1}
			logger.debug("Adding watch on file %s for job %s", filename, job_id)
			if not self.active:
				logger.debug("Watch for job %s means we're starting the timer.", job_id)
				self.periodic.start()
				self.active = True

	def remove_watch(self, job_id):
		filename = self.configuration.get_job_log_path(job_id)
		if self.watches.has_key(job_id):
			self.watches[job_id]['ref'] -= 1
			logger.debug("Decrementing reference count for %s - now %d.", job_id, self.watches[job_id]['ref'])
			if self.watches[job_id]['ref'] < 1:
				logger.debug("Removing watch of %s for job %s", filename, job_id)
				del self.watches[job_id]
				if len(self.watches.keys()) == 0:
					logger.debug("No more watches, so stopping the loop for the moment.")
					self.periodic.stop()
					self.active = False

	def trigger_watch(self, job_id):
		logger.debug("Watched job %s has changes - notifying people.", job_id)
		topic = self.configuration.get_job_message_pub_topic(job_id)
		pub.sendMessage(topic, job_id=job_id)

	def check_log_files(self):
		for job_id, meta in self.watches.iteritems():
			size = os.path.getsize(meta['filename'])
			#logger.debug("Checking file %s (old %d, new %d)", meta['filename'], meta['size'], size)
			if meta['size'] != size:
				self.watches[job_id]['size'] = size
				self.trigger_watch(job_id)

class JobLoggerAdapter(logging.LoggerAdapter):
	def __init__(self, logger, job_id, configuration, watcher):
		self.job_id = job_id
		self.configuration = configuration
		self.watcher = watcher
		super(JobLoggerAdapter, self).__init__(logger, {'job':job_id})

	def complete(self, state, summary):
		if self.watcher:
			# Trigger a file watch.
			self.watcher.trigger_watch(self.job_id)

	def takeover_file(self):
		# Close the file, if it's open.
		pub.sendMessage('job.takeover', job_id=self.job_id)
		# Open the file up again...
		job_file = self.configuration.get_job_log_path(self.job_id)
		if self.watcher:
			# Start watching it for changes.
			self.watcher.add_watch(self.job_id)
		# Return the open FP to the caller.
		return open(job_file, 'ab')

	def untakeover_file(self, fp):
		# Undo the takeover.
		fp.close()
		if self.watcher:
			# Stop watching.
			self.watcher.remove_watch(self.job_id)
			# Trigger a watch.
			self.watcher.trigger_watch(self.job_id)

	@staticmethod
	def setup_joblogger(configuration):
		joblogger = logging.getLogger('job')
		# TODO: This level should be adjustable, but how to make it
		# adjustable per job?
		joblogger.setLevel(logging.DEBUG)
		joblogger.addHandler(JobLoggingFileHandler(configuration))

class JobLoggingTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(JobLoggingTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(io_loop=self.io_loop)
		self.configuration.setup_job_watcher()
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
		super(JobLoggingTest, self).tearDown()

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

	def on_job_watch_update(self, job_id):
		self.stop(job_id)

	def test_watcher(self):
		pub.subscribe(self.on_job_watch_update, 'job.message')

		watcher = self.configuration.get_job_watcher()
		id1 = str(uuid.uuid4())
		job1logger = self.configuration.get_job_logger(id1)
		job1logger.debug('Test')

		watcher.add_watch(id1)

		# Log something else.
		job1logger.debug('More data')

		# Wait for the watcher to catch up.
		return_id = self.wait()
		self.assertEquals(return_id, id1, "Another job id returned... ?")

		# Watch again.
		watcher.add_watch(id1)

		# Stop watching - or, at least, decrement the reference count.
		watcher.remove_watch(id1)

		# Put some more data. This should still work, as we're still watching.
		job1logger.debug('More data')
		return_id = self.wait()
		self.assertEquals(return_id, id1, "Another job id returned... ?")

		# Now stop watching again.
		watcher.remove_watch(id1)

		# TODO: Check that we're not watching anymore properly...

		# Start watching again, which causes the timer to start again.
		watcher.add_watch(id1)

		# Log some more stuff.
		job1logger.debug('Third batch')

		# Wait for the watcher to catch up.
		return_id = self.wait()
		self.assertEquals(return_id, id1, "Another job id returned... ?")


import time

import paasmaker
from base import BasePeriodic, BasePeriodicTest

import colander

class JobsCleanerConfigurationSchema(colander.MappingSchema):
	max_age = colander.SchemaNode(colander.Integer(),
		title="Maximum job age",
		description="Maximum age for a job. Default to 7 days. After that time, the job is purged from the system.",
		default=86400 * 7,
		missing=86400 * 7)

class JobsCleaner(BasePeriodic):
	"""
	A plugin to remove old job entries from the jobs Redis.
	"""

	OPTIONS_SCHEMA = JobsCleanerConfigurationSchema()
	API_VERSION = "0.9.0"

	def on_interval(self, callback, error_callback):
		if not self.configuration.is_pacemaker():
			callback("Not a pacemaker, so not cleaning up jobs.")
			return

		self.callback = callback
		self.error_callback = error_callback
		self.cleaned_jobs = 0

		self._fetch_old_jobs()

	def _fetch_old_jobs(self):
		# Fetch a list of jobs older than the threshold.
		oldest_age = time.time() - self.options['max_age']
		self.configuration.job_manager.find_older_than(oldest_age, self._old_jobs_list, limit=20)

	def _old_jobs_list(self, jobs):
		if len(jobs) == 0:
			# No more old jobs to remove.
			self.logger.info("Completed cleaning up %d jobs.", self.cleaned_jobs)
			self.callback("Cleaned up %d jobs." % self.cleaned_jobs)
		else:
			# Start processing them.
			self.logger.info("Found %d old jobs, working on those.", len(jobs))
			self.old_jobs = jobs
			self._clean_job()

	def _clean_job(self):
		# Find a job to clean.
		try:
			job_id = self.old_jobs.pop()

			self.logger.debug("Removing %s." % job_id)
			self.cleaned_jobs += 1

			# Remove it, and call us when done.
			self.configuration.job_manager.delete_tree(job_id, self._clean_job)

		except IndexError, ex:
			# No more to process. Find some more.
			self._fetch_old_jobs()

class JobsCleanerTest(BasePeriodicTest):
	def setUp(self):
		super(JobsCleanerTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.periodic.jobs',
			'paasmaker.common.periodic.jobs.JobsCleaner',
			{},
			'Log Cleanup Plugin'
		)

		self.configuration.startup_job_manager(self.stop, self.stop)
		self.wait()

	def test_simple(self):
		# Should be no jobs.
		self.configuration.job_manager.find_older_than(time.time() + 10, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 0, "Was existing jobs.")

		# Submit a test job.
		self.configuration.job_manager.add_job('paasmaker.job.container', {}, "Example job.", self.stop)
		job_id = self.wait()

		# Check again.
		self.configuration.job_manager.find_older_than(time.time() + 10, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 1, "No job.")

		# Do a cleanup. This job should not be removed.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.jobs',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 0 ", self.message, "Incorrect message.")

		# Check again.
		self.configuration.job_manager.find_older_than(time.time() + 10, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 1, "No job.")

		# Change the plugins options. Use a negative time to get it to purge the database.
		self.configuration.plugins.register(
			'paasmaker.periodic.jobs',
			'paasmaker.common.periodic.jobs.JobsCleaner',
			{'max_age': -10},
			'Log Cleanup Plugin'
		)

		# Run it again.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.jobs',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 1 ", self.message)

		# Check again.
		self.configuration.job_manager.find_older_than(time.time() + 10, self.stop)
		jobs = self.wait()

		self.assertEquals(len(jobs), 0, "Job still present.")
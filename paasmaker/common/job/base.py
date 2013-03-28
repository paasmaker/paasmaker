#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker
from paasmaker.util.plugin import Plugin, MODE
from paasmaker.common.core import constants

import colander

class BaseJobOptionsSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseJobParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

class BaseJob(Plugin):
	"""
	A base class for Jobs. Provides helper and signalling function for jobs.
	"""
	MODES = {
		MODE.JOB: BaseJobParametersSchema()
	}
	OPTIONS_SCHEMA = BaseJobOptionsSchema()
	API_VERSION = "0.9.0"

	def configure(self, manager, job_id, metadata):
		"""
		Configure this job. This is an internal method called by
		the job manager after instantiating the job.

		:arg JobManager manager: The job manager instance.
		:arg str job_id: This job's ID.
		:arg dict metadata: Other job metadata.
		"""
		self.job_manager = manager
		self.job_id = job_id
		self.job_metadata = metadata

	# Helper signalling functions.
	def success(self, context, summary):
		"""
		Indicate that this job has succeeded. Stores the context
		passed to this function in the job tree. Also records the
		string summary passed for the job.

		:arg dict context: The output context to attach to the
			job tree.
		:arg str summary: The string summary of the job - a short
			message to say what happened.
		"""
		self._complete_job(constants.JOB.SUCCESS, context, summary)

	def failed(self, summary):
		"""
		Indicate that this job has failed. Supply a summary that
		describes why the job failed.

		:arg str summary: A short summary of why the job failed.
		"""
		self._complete_job(constants.JOB.FAILED, None, summary)

	def aborted(self, summary):
		"""
		Indicate that the abort sequence for this job is complete.
		You should supply a short summary of anything relevant
		to how the job was aborted.

		:arg str summary: A short summary.
		"""
		self._complete_job(constants.JOB.ABORTED, None, summary)

	def _complete_job(self, state, context, summary):
		self.job_manager.completed(self.job_id, state, context, summary)

	def _failure_callback(self, message, exception=None):
		"""
		A generic error callback that logs the message, optional
		exception, and then fails the job.
		"""
		self.logger.error(message)
		if exception:
			self.logger.error("Exception:", exc_info=exception)
		self.failed(message)

	# SUBCLASS OVERRIDE FUNCTIONS
	def start_job(self, context):
		"""
		Start doing the tasks required by your job. When your job
		is complete, you'll call either self.success() with your context
		updates and a summary of the job, or you will call self.failed()
		with a short summary of the failure. You should make use of the
		self.logger attribute to log anything as well.

		:arg dict context: A dict containing context values for this
			job tree.
		"""
		cls = str(self.__class__)
		raise NotImplementedError("You must implement start_job() - in %s" % cls)

	def abort_job(self):
		"""
		This is called to indicate that you should shut down or cancel
		any activities you had in motion, because the user has requested
		that you stop doing what you're doing or another job in the tree
		has failed. This will only be called if start_job had already
		been called and if you have not yet indicated success or failure.
		When you're done, call self.aborted() with a summary as appropriate.
		"""
		cls = str(self.__class__)
		raise NotImplementedError("You must implement abort_job() - in %s" % cls)

	def abort_handler(self, context):
		"""
		If implemented, and added to the manager as an abort handler,
		if the tree fails, this function is called with the jobs context.
		The order of abort handlers is not guaranteed at all, nor is the
		state of the context. Failures and exceptions here don't further
		alter the job tree, as it's already failed. You should also not
		call success(), failed(), or aborted(). Basically, do what you
		need to do and then finish up.

		:arg dict context: The context for this job tree.
		"""
		pass

class ContainerJob(BaseJob):
	"""
	A job that can be simply used to contain other jobs.
	"""
	def start_job(self, context):
		self.success({}, "All children jobs completed successfully.")

	def abort_job(self):
		self.aborted("Aborting this job due to request.")
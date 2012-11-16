

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
	MODES = [MODE.JOB]
	OPTIONS_SCHEMA = BaseJobOptionsSchema()
	PARAMETERS_SCHEMA = {MODE.JOB: BaseJobParametersSchema()}

	def configure(self, manager, job_id):
		self.job_manager = manager
		self.job_id = job_id

	# Helper signalling functions.
	def success(self, context, summary):
		self._complete_job(constants.JOB.SUCCESS, context, summary)

	def failed(self, summary):
		self._complete_job(constants.JOB.FAILED, None, summary)

	def aborted(self, summary):
		self._complete_job(constants.JOB.ABORTED, None, summary)

	def _complete_job(self, state, context, summary):
		self.job_manager.completed(self.job_id, state, context, summary)

	# SUBCLASS OVERRIDE FUNCTIONS
	def start_job(self, context):
		"""
		Start doing the tasks required by your job. When your job
		is complete, you'll call either self.success() with your context
		updates and a summary of the job, or you will call self.failed()
		with a short summary of the failure. You should make use of the
		self.logger attribute to log anything as well.
		"""
		raise NotImplementedError("You must implement start_job().")

	def abort_job(self):
		"""
		This is called to indicate that you should shut down or cancel
		any activities you had in motion, because the user has requested
		that you stop doing what you're doing or another job in the tree
		has failed. This will only be called if start_job had already
		been called and if you have not yet indicated success or failure.
		When you're done, call self.aborted() with a summary as appropriate.
		"""
		raise NotImplementedError("You must implement abort_job().")

class ContainerJob(BaseJob):
	"""
	A job that can be simply used to contain other jobs.
	"""
	def start_job(self, context):
		self.success({}, "All children jobs completed successfully.")

	def abort_job(self):
		self.aborted("Aborting this job due to request.")
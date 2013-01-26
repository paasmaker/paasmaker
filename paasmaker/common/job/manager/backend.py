
# CAUTION: TODO: It's expected that the JobBackend handles sending
# pub/sub messages by subscribing to job.status and sending it to
# other nodes. This works in the current implementation because
# the only backend is Redis, which supports Pub/Sub natively.
# Other backends might not, which might mean they need a different
# message broker (such as RabbitMQ).

class JobBackend(object):
	def __init__(self, configuration):
		self.configuration = configuration

	def setup(self, callback, error_callback):
		"""
		Setup anything you need, and call the callback when ready.
		"""
		raise NotImplementedError("You must implement setup().")

	def ensure_connected(self):
		"""
		Ensure that your backend is connected to the appropriate services.
		Eg, make sure the pub/sub connection is still active. This will
		be called periodically based on the configuration.
		"""
		raise NotImplementedError("You must implement ensure_connected().")

	def store_context(self, job_id, context, callback):
		"""
		Store the given context for the given job ID.
		Context is a dict of values, but may only be a partial
		update of values. job_id may not be the root job ID,
		so you should resolve that first. Calls the callback once complete.
		"""
		raise NotImplementedError("You must implement update_context().")

	def get_context(self, job_id, callback):
		"""
		Fetch all the context for the given job ID, and call
		the callback with it as a dict. job_id is resolved to the root
		first before querying the values.
		"""
		raise NotImplementedError("You must implement get_context().")

	def get_parent(self, job_id, callback):
		"""
		Fetch the parent of the given job. If the job is a parent job,
		return the same job ID. Calls the callback with the parent id.
		"""
		raise NotImplementedError("You must implement get_parent().")

	def get_root(self, job_id, callback):
		"""
		Fetch the root of the given job. Call the callback with the root
		job ID. If the called job_id is the root id, pass that to the
		callback.
		"""
		raise NotImplementedError("You must implement get_root().")

	def get_children(self, job_id, callback, state=None):
		"""
		Get all the direct children of the given job_id. Call the callback
		with a set of job ids that are the children. The result should
		be filtered by the state if supplied, which can be a single value
		or a set of values.
		"""
		raise NotImplementedError("You must implement get_children().")

	def exists(self, job_id, callback):
		"""
		Determine if a job exists. Call the callback with a boolean
		value that indicates if it does or doesn't exist.
		"""
		raise NotImplementedError("You must implement exists().")

	def add_job(self, node, job_id, parent_id, callback, **kwargs):
		"""
		Add a job with the given job_id, and the given parent_id. Parent
		might be none, indicating that this is a top level job.
		kwargs are parameters for this job, which should be stored as
		appropriate for this job. Callback will be called once the job
		is added.
		"""
		raise NotImplementedError("You must implement add_job().")

	def set_attrs(self, job_id, attrs, callback):
		"""
		Set the supplied attributes to the supplied value on the given
		job ID. Calls callback when complete with the complete latest job data.
		"""
		raise NotImplementedError("You must implement set_attrs().")

	def get_attr(self, job_id, attr, callback):
		"""
		Get the supplied attribute from the given job. Calls the callback
		with the value of that attribute.
		"""
		raise NotImplementedError("You must implement get_attr().")

	def get_job(self, job_id, callback):
		"""
		Gets all the values for the given job. Calls the callback with
		a dict of values.
		"""
		raise NotImplementedError("You must implement get_job().")

	def get_jobs(self, jobs, callback):
		"""
		Get the data for all the given jobs in one go, calling the callback
		with a dict. The keys are the job ids and the values a map of data.
		"""
		raise NotImplementedError("You must implement get_jobs().")

	def tag_job(self, job_id, tag, callback):
		"""
		Tag a job with the given tag. If the supplied job_id isn't a root
		ID, find and tag that root ID instead. tag might be a list of tags
		to add to the system.
		"""
		raise NotImplementedError("You must implement tag_job().")

	def find_by_tag(self, tag, callback, limit=None):
		"""
		Return a set of parent jobs by the given tag. Call the callback
		with a list of job ids that match - which should only ever be
		root jobs. If possible, sort the returned jobs by their time in
		reverse, so most recent jobs first. This is designed for the front
		end to be able to list jobs to display to users, not for locating
		jobs that are ready to run or other tasks.
		"""
		raise NotImplementedError("You must implement find_by_tag().")

	def find_older_than(self, age, callback, limit=None):
		"""
		Return a set of root jobs that are older than the given unix timestamp.
		Call the callback with a list of job IDs that match. If possible, you
		should sort the list so the most recent of those jobs appears first.
		This is designed to clean up old jobs from the system.

		:arg int age: The unix timestamp that the jobs should be older than.
		:arg callable callback: The callback to call with the jobs.
		:arg int limit: Limit the return to a number of results.
		"""
		raise NotImplementedError("You must implement find_older_than().")

	def get_ready_to_run(self, node, waiting_state, success_state, callback):
		"""
		Return a set of jobs that are ready to run for the given node.
		"Ready to run" is defined as jobs on the node who are currently in the
		waiting state, and whose children are all in the supplied success state.
		Call the callback with a set of jobs that match.
		"""
		raise NotImplementedError("You must implement get_ready_to_run().")

	def set_state_tree(self, job_id, from_state, to_state, callback, node=None):
		"""
		Set the entire tree that job_id is in to the supplied state. This is designed
		to move a tree of jobs from 'NEW' to 'WAITING' state for execution. The backend should
		do this blindly, so the caller must use with caution. The backend should also
		locate the root job before starting this.
		"""
		raise NotImplementedError("You must implement set_state_tree().")

	def get_tree(self, job_id, callback, state=None, node=None):
		"""
		Get the entire tree for job_id. The root job should be resolved internally.
		If state is supplied, return all the jobs in those states. The result is
		just a flat list of the jobs - you don't need to nest or order them.
		"""
		raise NotImplementedError("You must implement get_tree().")

	def delete_tree(self, job_id, callback):
		"""
		Delete the entire tree for the given job ID. The job should be resolved
		to a root job internally before getting started. Call the callback with
		no arguments when done.
		"""
		raise NotImplementedError("You must implement delete_tree().")

	def get_node_jobs(self, node, callback, state=None):
		"""
		Get a list of jobs on the given node. These could be anywhere in a job
		tree. Optionally limit it to the list of states supplied.

		:arg str node: The node UUID to fetch the jobs for.
		:arg callable callback: The callback to call with the list of job IDs.
		:arg str|list state: The states to limit to.
		"""
		raise NotImplementedError("You must implement get_node_jobs().")

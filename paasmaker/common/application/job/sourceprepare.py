
import paasmaker

class SourcePreparerJob(paasmaker.util.jobmanager.JobRunner):
	def __init__(self, configuration, prepare):
		self.configuration = configuration
		# Take a copy of the list.
		self.prepare = list(prepare)
		self.prepare.reverse()

	def get_job_title(self):
		return "Source code preparer"

	def start_job(self):
		root = self.get_root_job()

		# This is the working directory for this.
		self.path = root.source_path
		self.environment = root.environment

		logger = self.job_logger()

		# We need to go over the prepare entries in order,
		# and process them, signalling failure when one fails,
		# and success when we have none left.
		# CAUTION: The environment is not shared between commands.
		if len(self.prepare) == 0:
			logger.info("No tasks to progress, so successfully completed.")
			self.finished_job('SUCCESS', 'No tasks to process.')
		else:
			logger.info("Running through %d tasks.", len(self.prepare))
			task = self.prepare.pop()
			self.do_prepare_task(task)

	def find_next_task(self):
		# Find the next task.
		logger = self.job_logger()
		try:
			next_task = self.prepare.pop()
			self.do_prepare_task(next_task)
		except IndexError, ex:
			# No more tasks to pop. So we're done!
			logger.info("Completed all tasks successfully.")
			self.finished_job('SUCCESS', 'Completed all prepare tasks successfully.')

	def do_prepare_task(self, task):
		# If the task matches a plugin, run and execute that.
		logger = self.job_logger()
		if self.configuration.plugins.exists(task):
			logger.info("Starting up plugin %s...", task)
			plugin = self.configuration.plugins.instantiate(task, {'path': self.path}, self.logger)
			plugin.prepare(self.plugin_success, self.plugin_failure)
		else:
			# It's a shell command. Set it up and do it.
			logger.info("Running command: %s", task)
			log_fp = logger.takeover_file()

			# The callback to handle success/failure.
			def callback(code):
				logger.untakeover_file(log_fp)
				logger.info("Command result: %d" % code)
				if code == 0:
					self.find_next_task()
				else:
					logger.error("Command did not complete successfully. Aborting.")
					self.finished_job('FAILED', 'Command did not complete successfully. Aborting.')

			# And the runner that runs the task.
			runner = paasmaker.util.Popen(task,
				stdout=log_fp,
				stderr=log_fp,
				on_exit=callback,
				cwd=self.path,
				io_loop=self.configuration.io_loop,
				env=self.environment)

	def plugin_success(self):
		self.find_next_task()

	def plugin_failure(self, message):
		self.finished_job('FAILED', message)
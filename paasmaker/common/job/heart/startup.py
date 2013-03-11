
import os
import urlparse

from ..base import BaseJob
from paasmaker.util.plugin import MODE

import paasmaker
from paasmaker.common.core import constants

import colander

class InstanceStartupJobSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.String())

class InstanceStartupJob(BaseJob):
	"""
	A job to start the instance on this node.
	"""
	MODES = {
		MODE.JOB: InstanceStartupJobSchema()
	}

	def start_job(self, context):
		self.instance_id = self.parameters['instance_id']
		self.instance_data = self.configuration.instances.get_instance(self.instance_id)

		self.logger.info("Starting up instance %s.", self.instance_id)

		runtime_name = self.instance_data['instance_type']['runtime_name']
		plugin_exists = self.configuration.plugins.exists(
			runtime_name,
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
		)

		if not plugin_exists:
			error_message = "Runtime %s does not exist." % runtime_name
			self.logger.error(error_message)
			self.failed(error_message)
		else:
			# Update instance state to starting.
			self.instance_data['instance']['state'] = constants.INSTANCE.STARTING
			self.configuration.instances.save()

			runtime = self.configuration.plugins.instantiate(
				runtime_name,
				paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
				self.instance_data['instance_type']['runtime_parameters'],
				self.logger
			)

			# Sanity check - see if this instance is already running.
			def not_running(message, exception=None):
				# Make sure the allocated port is not already in use.
				free_to_start = True
				if not self.instance_data['instance_type']['standalone']:
					port_checker = paasmaker.util.port.FreePortFinder()
					if port_checker.in_use(self.instance_data['instance']['port']):
						self.logger.error("Found allocated port %d was already in use.", self.instance_data['instance']['port'])
						free_to_start = False

						# Make a log entry in that instances log file for later reference.
						instance_logger = self.configuration.get_job_logger(self.instance_id)
						instance_logger.error("Found allocated port %d was already in use.", self.instance_data['instance']['port'])
						instance_logger.error("And the instance is not running.")
						instance_logger.error("Aborting startup.")
						instance_logger.finished()

				if free_to_start:
					# Cool, go ahead and start it.
					runtime.start(
						self.instance_id,
						self.success_callback,
						self.failure_callback
					)
				else:
					# Something was blocking this startup.
					# Abort, and place it into the error state.
					self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
					self.configuration.instances.save()

					self.logger.error("Found that the port allocated was already in use.")
					self.failed("Found that the port allocated was already in use.")

			def is_running(message):
				# It's apparently running. No reason to start it.
				# Although one should ask why we got here.
				self.logger.info("Instance is already running. No action taken.")
				self.logger.warning("We don't know why it was already running.")

				self.instance_data['instance']['state'] = constants.INSTANCE.RUNNING
				self.configuration.instances.save()

				self.success({state_key: constants.INSTANCE.RUNNING}, "Found instance already running.")

			# See if it's running.
			self.logger.info("Checking to see if the instance is already running.")
			runtime.status(
				self.instance_id,
				is_running,
				not_running
			)

	def success_callback(self, message):
		# We're up and running!
		# Record the instance state.
		self.instance_data['instance']['state'] = constants.INSTANCE.RUNNING
		self.configuration.instances.save()

		self.logger.info("Instance started successfully.")
		state_key = "state-%s" % self.instance_id
		self.success({state_key: constants.INSTANCE.RUNNING}, "Started instance successfully.")

	def failure_callback(self, message, exception=None):
		self.logger.error(message)
		if exception:
			self.logger.error(exception)
		self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
		self.configuration.instances.save()

		# Include the log entries from that instance.
		# TODO: Only include some of this data.
		instance_log_file = self.configuration.get_job_log_path(self.instance_id, False)
		if os.path.exists(instance_log_file):
			fp = open(instance_log_file, 'r')
			self.logger.info("Instance log file:\n%s", fp.read())
			fp.close()

		self.failed(message)
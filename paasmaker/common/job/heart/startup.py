
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
	PARAMETERS_SCHEMA = {MODE.JOB: InstanceStartupJobSchema()}

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
			self.configuration.send_instance_status(self.instance_id, constants.INSTANCE.STARTING)

			runtime = self.configuration.plugins.instantiate(
				runtime_name,
				paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
				self.instance_data['instance_type']['runtime_parameters'],
				self.logger
			)

			runtime.start(
				self.instance_id,
				self.success_callback,
				self.failure_callback
			)

	def success_callback(self, message):
		# We're up and running!
		# Record the instance state.
		self.instance_data['instance']['state'] = constants.INSTANCE.RUNNING
		self.configuration.instances.save()
		self.configuration.send_instance_status(self.instance_id, constants.INSTANCE.RUNNING)

		self.logger.info("Instance started successfully.")
		self.success({self.instance_id: constants.INSTANCE.RUNNING}, "Started instance successfully.")

	def failure_callback(self, message):
		self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
		self.configuration.instances.save()
		self.configuration.send_instance_status(self.instance_id, constants.INSTANCE.ERROR)

		self.logger.error(message)
		self.failed(message)
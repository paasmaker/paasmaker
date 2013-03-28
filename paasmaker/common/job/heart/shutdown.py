#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import urlparse

from ..base import BaseJob
from paasmaker.util.plugin import MODE

import paasmaker
from paasmaker.common.core import constants

import colander

class InstanceShutdownJobSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.String())

class InstanceShutdownJob(BaseJob):
	"""
	A job to stop the instance on this node.
	"""
	MODES = {
		MODE.JOB: InstanceShutdownJobSchema()
	}

	def start_job(self, context):
		self.instance_id = self.parameters['instance_id']
		self.instance_data = self.configuration.instances.get_instance(self.instance_id)

		self.logger.info("Shutting down instance %s.", self.instance_id)

		runtime_name = self.instance_data['instance_type']['runtime_name']
		plugin_exists = self.configuration.plugins.exists(
			runtime_name,
			paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
		)

		if not plugin_exists:
			error_message = "Runtime %s does not exist. How did you start this application?" % runtime_name
			self.logger.error(error_message)
			self.failed(error_message)
		else:
			runtime = self.configuration.plugins.instantiate(
				runtime_name,
				paasmaker.util.plugin.MODE.RUNTIME_EXECUTE,
				self.instance_data['instance_type']['runtime_parameters'],
				self.logger
			)

			runtime.stop(
				self.instance_id,
				self.success_callback,
				self.failure_callback
			)

	def success_callback(self, message):
		# We're shut down.
		# Record the instance state.
		self.instance_data['instance']['state'] = constants.INSTANCE.STOPPED
		self.configuration.instances.save()

		self.logger.info("Instance stopped successfully.")
		state_key = "state-%s" % self.instance_id
		self.success({state_key: constants.INSTANCE.STOPPED}, "Stopped instance successfully.")

	def failure_callback(self, message, exception=None):
		self.logger.error(message)
		if exception:
			self.logger.error(exception)
		self.instance_data['instance']['state'] = constants.INSTANCE.ERROR
		self.configuration.instances.save()

		self.failed(message)
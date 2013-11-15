#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import glob
import uuid
import time
import logging

import paasmaker
from base import BasePeriodic, BasePeriodicTest

import colander

class InstancesCheckConfigurationSchema(colander.MappingSchema):
	pass

class InstancesCheck(BasePeriodic):
	"""
	A plugin to run a running instances check periodically,
	to make sure they're still actually running.
	"""
	OPTIONS_SCHEMA = InstancesCheckConfigurationSchema()
	API_VERSION = "0.9.0"

	def on_interval(self, callback, error_callback):
		if not self.configuration.is_heart():
			callback("This node is not a heart, so not checking instances on it.")
		else:
			# Just ask the instance manager to handle this.
			def instance_check_complete(adjusted_instances):
				callback("Found %d instances that had changed state." % len(adjusted_instances))
				# end of instance_check_complete()

			self.configuration.instances.check_instances_runtime(
				self.logger,
				instance_check_complete
			)

class InstancesCheckTest(BasePeriodicTest):
	def setUp(self):
		super(InstancesCheckTest, self).setUp()

		# We need to act like a heart.
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['heart'], io_loop=self.io_loop)

		self.configuration.plugins.register(
			'paasmaker.periodic.instances',
			'paasmaker.common.periodic.instances.InstancesCheck',
			{},
			'Instances Check Plugin'
		)

		self.logger = logging.getLogger('job')
		# Prevent propagation to the parent. This prevents extra messages
		# during unit tests.
		self.logger.propagate = False
		# Clean out all handlers. Otherwise multiple tests fail.
		self.logger.handlers = []

		paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(self.configuration)

	def test_simple(self):
		# Just run it. It should succeed. We test the actual
		# functionality in the Register Root job test.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.instances',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 0 ", self.message, "Wrong message returned.")

import unittest
import paasmaker
import uuid
import logging
import colander
import json
import os

from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing
from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class InstanceRegisterSchema(colander.MappingSchema):
	# We don't validate the contents of below, but we do make sure
	# that we're at least supplied them.
	instance = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	instance_type = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	application_version = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	application = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")
	environment = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance data")

class InstanceExitController(BaseController):
	"""
	Simple controller to accept an exit status from a script,
	designed to be used by runtimes to indicate exiting easily.
	Allows anonymous access, but is authorized internally by a unique key.
	"""
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self, instance_id, unique_key, code):
		# Force response to be JSON.
		self._set_format('json')

		# See if we have the instance metadata.
		if not self.configuration.instances.has_instance(instance_id):
			self.add_error("No such instance %s" % instance_id)
		else:
			instance = self.configuration.instances.get_instance(instance_id)

			# In the runtime set is a list of unique keys.
			# The supplied unique key must be in that set.
			if instance['runtime'].has_key('exit') and \
				unique_key in instance['runtime']['exit']['keys']:
				# Found something valid. Remove the key, it's one
				# use only.
				instance['runtime']['exit']['keys'].remove(unique_key)

				# Based on the code, broadcast the status.
				code = int(code)
				if code == 0:
					instance['instance']['state'] = constants.INSTANCE.STOPPED
					self.configuration.send_instance_status(instance_id, constants.INSTANCE.STOPPED)
				else:
					instance['instance']['state'] = constants.INSTANCE.ERROR
					self.configuration.send_instance_status(instance_id, constants.INSTANCE.ERROR)

				self.add_data('success', True)
				self.configuration.instances.save()
			else:
				self.add_error('Invalid credentials supplied.')

		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		# Url is: /instance/exit/instance_id/unique_key/exit_code
		routes.append((r"/instance/exit/([-a-zA-Z0-9]+)/([-a-zA-Z0-9]+)/(\d+)", InstanceExitController, configuration))
		return routes

	def test_exit(self):
		instance = self.create_sample_application(self.configuration, 'paasmaker.runtime.shell', {}, '1', 'tornado-simple')

		request = paasmaker.common.api.instanceregister.InstanceRegisterAPIRequest(self.configuration)
		request.set_instance(instance)
		request.set_target(instance.node)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		# Wait for the register job to complete.
		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		result = self.wait()
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Job did not succeed.")

		# Now, listen for intance updates.
		pub.subscribe(self.on_instance_status, self.configuration.get_instance_status_pub_topic(instance.instance_id))

		# Set up the exit handler.
		baseruntime = paasmaker.heart.runtime.BaseRuntime(
			self.configuration,
			paasmaker.util.plugin.MODE.RUNTIME_ENVIRONMENT,
			{}, {}, 'paasmaker.runtime.base')
		baseruntime.generate_exit_report_command(instance.instance_id)

		# From that exit report, hit up the supplied URL.
		instance_data = self.configuration.instances.get_instance(instance.instance_id)

		self.http_client.fetch(self.get_url(instance_data['runtime']['exit']['url'] + '0'), self.noop)

		state = self.wait()
		self.assertEquals(state.state, constants.INSTANCE.STOPPED)

		# Try it again, with a zero exit code - it will fail because the key has already been used.
		self.http_client.fetch(self.get_url(instance_data['runtime']['exit']['url'] + '0'), self.stop)
		response = self.wait()
		# Should be an error message about invalid credentials.
		self.assertIn("credentials", response.body)

		# Generate a new one, and exit with a non-zero response code.
		baseruntime.generate_exit_report_command(instance.instance_id)

		instance_data = self.configuration.instances.get_instance(instance.instance_id)

		self.http_client.fetch(self.get_url(instance_data['runtime']['exit']['url'] + '1'), self.noop)

		state = self.wait()
		self.assertEquals(state.state, constants.INSTANCE.ERROR)
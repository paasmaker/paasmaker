
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

class InstanceRegisterController(BaseController):
	"""
	Controller to register an instance with the heart.
	We call this "registration" because it's making the heart
	aware of the instance. Other controllers handle actually
	starting and stopping the instance.
	"""
	AUTH_METHODS = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	def post(self):
		self.validate_data(InstanceRegisterSchema())

		# Allocate a port.
		port = self.configuration.get_free_port()
		self.add_data('port', port)

		collected_data = {}
		collected_data['instance'] = self.param('instance')
		collected_data['instance_type'] = self.param('instance_type')
		collected_data['application_version'] = self.param('application_version')
		collected_data['application'] = self.param('application')
		collected_data['environment'] = self.param('environment')

		collected_data['instance']['port'] = port

		instance_id = collected_data['instance']['instance_id']

		if self.configuration.instances.has_instance(instance_id):
			self.add_error("Instance id %s is already registered on this node." % instance_id)
		else:
			self.configuration.instances.add_instance(instance_id, collected_data)
			self.add_data('instance_id', instance_id)

			# Create a job to prepare it. And send back the job ID.
			registerjob = paasmaker.common.job.heart.registerjob.RegisterJob(self.configuration, instance_id)
			manager = self.configuration.job_manager
			manager.add_job(registerjob)
			self.add_data('job_id', registerjob.job_id)

			# Start off the job... well, soon, anyway.
			manager.evaluate()

		# Return the response.
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/instance/register", InstanceRegisterController, configuration))
		return routes

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

class InstanceRegisterControllerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = InstanceRegisterController.get_routes({'configuration': self.configuration})
		routes.extend(InstanceExitController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def on_instance_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_registration(self):
		instance = self.create_sample_application(self.configuration, 'paasmaker.runtime.shell', {}, '1', 'tornado-simple')

		request = paasmaker.common.api.instanceregister.InstanceRegisterAPIRequest(self.configuration)
		request.set_instance(instance)
		request.set_target(instance.node)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('port'), "Response did not contain a port.")
		self.assertTrue(response.data.has_key('job_id'), "Missing job ID in response.")

		# Wait for the register job to complete.
		job_id = response.data['job_id']
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(job_id))

		result = self.wait()
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Job did not succeed.")

		# Reload the instance and make sure the port was set.
		instance = self.configuration.get_database_session().query(paasmaker.model.ApplicationInstance).get(instance.id)
		self.assertEquals(response.data['port'], instance.port, "Port was not set.")

		# Try to register again. This will fail.
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertIn("already registered", response.errors[0], "Incorrect error message.")

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
		baseruntime.generate_exit_report_command(self.configuration,
			self.configuration.instances,
			instance.instance_id)

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
		baseruntime.generate_exit_report_command(self.configuration,
			self.configuration.instances,
			instance.instance_id)

		instance_data = self.configuration.instances.get_instance(instance.instance_id)

		self.http_client.fetch(self.get_url(instance_data['runtime']['exit']['url'] + '1'), self.noop)

		state = self.wait()
		self.assertEquals(state.state, constants.INSTANCE.ERROR)
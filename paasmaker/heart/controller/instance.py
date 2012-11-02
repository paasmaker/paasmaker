
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
	auth_methods = [BaseController.NODE]

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

class InstanceRegisterControllerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = InstanceRegisterController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_registration(self):
		session = self.configuration.get_database_session()
		instance = self.create_sample_instance(session, 'paasmaker.runtime.php', {}, '5.3')

		request = paasmaker.common.api.instanceregister.InstanceRegisterAPIRequest(self.configuration)
		request.set_instance(instance)
		request.set_target(instance.node)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('port'), "Response did not contain a port.")

		# Reload the instance and make sure the port was set.
		session.refresh(instance)
		self.assertEquals(response.data['port'], instance.port)

		# Try to register again. This will fail.
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertIn("already registered", response.errors[0], "Incorrect error message.")

	def create_sample_instance(self, session, runtime_name, runtime_parameters, runtime_version):
		# Pack up the tornado simple test application.
		temptarball = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.tar.gz')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')
		command = ['tar', 'zcvf', temptarball, '.']

		tarrer = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary tarball file.")

		# Make a node (ie, us) to run on.
		our_uuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(our_uuid)
		node = paasmaker.model.Node('instance_register_test', 'localhost', self.get_http_port(), our_uuid, constants.NODE.ACTIVE)
		session.add(node)
		session.commit()

		# And the remainder of the models to test with.
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''
		application_version.source_path = "paasmaker://%s/%s" % (our_uuid, temptarball)
		application_version.source_checksum = 'dummychecksumhere'

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = runtime_name
		instance_type.runtime_parameters = runtime_parameters
		instance_type.runtime_version = runtime_version
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.state = constants.INSTANCE_TYPE.PREPARED

		session.add(instance_type)
		session.commit()

		# And now, an instance on that node.
		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.state = constants.INSTANCE.ALLOCATED

		session.add(instance)
		session.commit()

		return instance
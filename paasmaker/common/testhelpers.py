#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import time
import os
import uuid
import logging
import traceback

import paasmaker

import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class TestHelpers(object):
	# A collection of functions that can be mixed into unit tests
	# to provide useful things for tests. Most assume that you're an
	# AsyncTestCase or subclass.

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()

	def noop(self, argument=None):
		pass

	def dump_job_tree(self, job_id):
		self.configuration.job_manager.debug_dump_job_tree(job_id, self.stop)

	def pack_sample_application(self, application):
		# Pack up the tornado simple test application.
		temptarball = os.path.join(self.configuration.get_scratch_path_exists('packed'), 'testapplication.tar.gz')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../misc/samples/%s' % application)
		command = ['tar', 'zcvf', temptarball, '.']

		tarrer = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary tarball file.")

		return temptarball

	def create_sample_application(self,
			configuration,
			runtime_name,
			runtime_parameters,
			runtime_version,
			application):
		# Pack up the tornado simple test application.
		temptarball = self.pack_sample_application(application)

		# If supplied a config object, use that to create the instance.
		# Otherwise, do it in a new one - because we want to make sure
		# hearts can work without being a pacemaker.
		temp_configuration = False
		if not configuration:
			temp_configuration = True
			configuration = paasmaker.common.configuration.ConfigurationStub(
				port=self.get_http_port(),
				modules=['pacemaker'],
				io_loop=self.io_loop)

		configuration.get_database_session(self.stop, None)
		session = self.wait()

		# Make a node (ie, us) to run on.
		# our_uuid = str(uuid.uuid4())
		# self.configuration.set_node_uuid(our_uuid)
		# node = paasmaker.model.Node('instance_register_test', 'localhost', configuration.get_flat('http_port'), our_uuid, paasmaker.common.core.constants.NODE.ACTIVE)
		# session.add(node)
		# session.commit()

		# And the remainder of the models to test with.
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		service = paasmaker.model.Service()
		service.application = application
		service.name = 'test'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''
		application_version.source_path = "paasmaker://%s/%s" % (self.configuration.get_node_uuid(), os.path.basename(temptarball))
		application_version.source_checksum = 'dummychecksumhere'
		application_version.source_package_type = 'tarball'
		application_version.state = paasmaker.common.core.constants.VERSION.PREPARED
		application_version.scm_name = 'paasmaker.scm.zip'
		application_version.scm_parameters = {}

		application_version.services.append(service)

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
		instance_type.standalone = False

		session.add(instance_type)
		session.commit()

		return instance_type

	def create_sample_application_instance(self, configuration, session, instance_type, node):
		# If supplied a config object, use that to create the instance.
		# Otherwise, do it in a new one - because we want to make sure
		# hearts can work without being a pacemaker.
		temp_configuration = False
		if not configuration:
			temp_configuration = True
			configuration = paasmaker.common.configuration.ConfigurationStub(
				port=self.get_http_port(),
				modules=['pacemaker'],
				io_loop=self.io_loop)

		# And now, an instance on that node.
		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.state = paasmaker.common.core.constants.INSTANCE.ALLOCATED

		session.add(instance)
		session.commit()

		if temp_configuration:
			configuration.cleanup()

		return instance

	def add_simple_node(self, session, tags, configuration):
		ctr = 1
		if configuration.get_node_uuid() is None:
			configuration.set_node_uuid(str(uuid.uuid4()))
		node = paasmaker.model.Node(name='test%d' % ctr,
				route='%d.local.paasmaker.net' % ctr,
				apiport=configuration.get_flat('http_port'),
				uuid=configuration.get_node_uuid(),
				state=paasmaker.common.core.constants.NODE.ACTIVE)
		node.heart = True
		node.pacemaker = True
		node.tags = tags
		session.add(node)
		session.commit()

		return node

	def create_sample_instance_data(self,
			configuration,
			runtime_name,
			runtime_parameters,
			runtime_version,
			application):
		instance_type = self.create_sample_application(configuration,
			runtime_name,
			runtime_parameters,
			runtime_version,
			application)
		configuration.get_database_session(self.stop, None)
		session = self.wait()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(instance_type.id)
		node = self.add_simple_node(
			session,
			{
				'node': {},
				'runtimes': {
					runtime_name: [runtime_version]
				}
			},
			configuration
		)
		instance = self.create_sample_application_instance(
			configuration,
			session,
			instance_type,
			node
		)

		flat = instance.flatten_for_heart()

		return flat

class MultipaasTestHandler(object):
	def __init__(self, testcase):
		self.testcase = testcase

	def __enter__(self):
		pass

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type is not None and hasattr(self.testcase, 'multipaas'):
			# An exception occurred.
			# We don't interfere with it, but we do
			# pause for a moment so that the user can
			# interact with the MultiPaas and figure out the
			# bug.
			summary = self.testcase.multipaas.get_summary()
			print
			print "Something went wrong:"
			print exc_val
			traceback.print_tb(exc_tb)
			print "Connect to the multipaas here to debug this:"
			print "http://localhost:%d/" % summary['configuration']['master_port']
			print "Using username and password: %s / %s" % (self.testcase.USERNAME, self.testcase.PASSWORD)
			close = raw_input("Press enter to close and destroy this cluster and continue.")

		# Don't return anything, we want the exception to bubble.

class BaseMultipaasTest(tornado.testing.AsyncTestCase, TestHelpers):
	USERNAME = 'multipaas'
	PASSWORD = 'multipaas'

	def add_multipaas_node(self, **kwargs):
		if not hasattr(self, 'multipaas'):
			self.multipaas = paasmaker.util.multipaas.MultiPaas()

		self.multipaas.add_node(**kwargs)

	def start_multipaas(self):
		# Start it running.
		self.multipaas.start_nodes()

		self.executor = self.multipaas.get_executor()

		# Create a user, role, workspace, and allocate that role.
		user_result = self.executor.run(['user-create', self.USERNAME, 'multipaas@paasmaker.com', 'Multi Paas', self.PASSWORD])
		role_result = self.executor.run(['role-create', 'Administrator', 'ALL'])
		workspace_result = self.executor.run(['workspace-create', 'Test', 'test', '{}'])

		self.executor.run(['role-allocate', role_result['role']['id'], user_result['user']['id']])

		self.mp_user_id = user_result['user']['id']
		self.mp_role_ud = role_result['role']['id']
		self.mp_workspace_id = workspace_result['workspace']['id']

	def tearDown(self):
		if hasattr(self, 'multipaas'):
			self.multipaas.stop_nodes()
			self.multipaas.destroy()
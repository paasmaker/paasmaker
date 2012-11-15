
import time
import os
import uuid

import paasmaker

class TestHelpers(object):
	# A collection of functions that can be mixed into unit tests
	# to provide useful things for tests. Most assume that you're an
	# AsyncTestCase or subclass.

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()

	def noop(self, argument=None):
		pass

	def dump_job_tree(self, job_id, backend):
		def on_job_full(jobs):
			# Righto! Now we can sort and build this into a tree.
			results = []
			for job in jobs.values():
				results.append("R:%(root_id)s P:%(parent_id)s J:%(job_id)s => S:%(state)s N:%(node)s" % job)
			results.sort()
			for result in results:
				print result
			self.stop()

		def on_root_tree(tree):
			# Now fetch the complete job data on all these elements.
			backend.get_jobs(tree, on_job_full)

		def on_found_root(root_id):
			# Find the root's entire tree.
			backend.get_tree(root_id, on_root_tree)

		backend.get_root(job_id, on_found_root)

	def pack_sample_application(self, application):
		# Pack up the tornado simple test application.
		temptarball = os.path.join(self.configuration.get_flat('scratch_directory'), 'testapplication.tar.gz')
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

		session = configuration.get_database_session()

		# Make a node (ie, us) to run on.
		our_uuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(our_uuid)
		node = paasmaker.model.Node('instance_register_test', 'localhost', self.get_http_port(), our_uuid, paasmaker.common.core.constants.NODE.ACTIVE)
		session.add(node)
		session.commit()

		# And the remainder of the models to test with.
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'

		service = paasmaker.model.Service()
		service.workspace = workspace
		service.name = 'test'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

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
		instance_type.state = paasmaker.common.core.constants.INSTANCE_TYPE.PREPARED

		session.add(instance_type)
		session.commit()

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

	def create_sample_instance_data(self,
			configuration,
			runtime_name,
			runtime_parameters,
			runtime_version,
			application):
		instance = self.create_sample_application(configuration,
			runtime_name,
			runtime_parameters,
			runtime_version,
			application)

		flat = instance.flatten_for_heart()

		return flat
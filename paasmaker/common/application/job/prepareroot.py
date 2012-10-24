
import os

import paasmaker
from manifestreader import ManifestReaderJob

import tornado
from pubsub import pub

class ApplicationPrepareRootJob(paasmaker.util.jobmanager.ContainerJob):
	def __init__(self, configuration, name, manifest, workspace_id, application_id=None, uploaded_file=None):
		self.configuration = configuration
		self.name = name
		self.manifest = manifest
		self.session = self.configuration.get_database_session()
		self.uploaded_file = uploaded_file

		# Load up the workspace and application, via our session, so we don't have
		# detached session issues.
		self.workspace = self.session.query(paasmaker.model.Workspace).get(workspace_id)
		if application_id:
			self.application = self.session.query(paasmaker.model.Application).get(application_id)
		else:
			self.application = None

		# Environment starts as a copy of Paasmaker's environment.
		# TODO: This may or may not be a good idea...
		self.environment = {}
		for key, value in os.environ.iteritems():
			self.environment[key] = value

	def get_job_title(self):
		return "Prepare container for %s" % self.name

	def start_job(self):
		# We should now have a 'package' attribute on our object.
		# Record that into the version.

		logger = self.job_logger()

		logger.info("Finalising package for %s" % self.name)

		# TODO: Handle the ability to place packages in custom places (eg Amazon S3, shared filesystem, etc)
		version = self.version
		self.session.refresh(version)
		version.source_path = "paasmaker://%s/%s" % (self.configuration.get_node_uuid(), self.package)
		self.session.add(version)
		self.session.commit()

		self.finished_job('SUCCESS', "Completed successfully.")

	@staticmethod
	def start(configuration, name, manifest, workspace_id, application_id=None, uploaded_file=None):
		# The root job.
		root = ApplicationPrepareRootJob(configuration, name, manifest, workspace_id, application_id=application_id, uploaded_file=uploaded_file)
		configuration.job_manager.add_job(root)

		# The manifest reader. This queues up more jobs on success.
		manfiest_reader_job = ManifestReaderJob(configuration)
		configuration.job_manager.add_job(manfiest_reader_job)
		configuration.job_manager.add_child_job(root, manfiest_reader_job)

		# Return the root job so we can track this.
		return root

class PrepareJobTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(PrepareJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(PrepareJobTest, self).tearDown()

	def on_job_status(self, job_id, state, source):
		self.stop({'job_id': job_id, 'state': state, 'source': source})

	def on_job_catchall(self, **kwargs):
		# This is for debugging.
		#print str(kwargs)
		pass

	def test_simple(self):
		# Create a zip file for us to use.
		# Cleanup will destroy this folder for us.
		tempzip = os.path.join(self.configuration.get_flat('scratch_directory'), 'packertest.zip')
		command_log = os.path.join(self.configuration.get_flat('scratch_directory'), 'packertest.log')
		command_log_fp = open(command_log, 'w')
		workingdir = os.path.normpath(os.path.dirname(__file__) + '/../../../../misc/samples/tornado-simple')
		# We're cheating a bit here - we'd normally have to figure out how to extract this...
		manifest = os.path.normpath(os.path.dirname(__file__) + '/../../../../misc/samples/tornado-simple/manifest.yml')
		command = ['zip', tempzip, 'app.py', 'manifest.yml']

		zipper = paasmaker.util.Popen(command,
			on_exit=self.stop,
			stderr=command_log_fp,
			stdout=command_log_fp,
			cwd=workingdir,
			io_loop=self.io_loop)

		code = self.wait()

		self.assertEquals(code, 0, "Unable to create temporary zip file.")

		# Now let's get started...
		s = self.configuration.get_database_session()
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Work Zone'
		s.add(workspace)
		s.commit()

		root_job = ApplicationPrepareRootJob.start(self.configuration, 'foo.com', manifest, workspace.id, uploaded_file=tempzip)

		root_job_id = root_job.job_id

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')

		# And make it work.
		self.configuration.job_manager.evaluate()

		result = self.wait()

		self.assertEquals(result['state'], 'SUCCESS', "Should have succeeded.")
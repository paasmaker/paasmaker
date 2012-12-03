
import os
import subprocess

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class ApplicationPrepareRootJob(BaseJob):
	@staticmethod
	def setup(configuration, name, manifest, workspace_id, callback, application_id=None, uploaded_file=None):
		# Set up the context.
		context = {}
		context['manifest_file'] = manifest
		context['application_name'] = name
		context['workspace_id'] = workspace_id
		context['application_id'] = application_id
		context['uploaded_file'] = uploaded_file
		context['environment'] = {}

		tags = []
		tags.append('workspace:%d' % workspace_id)

		def on_manifest_reader_added(root_job_id, manifest_reader_job_id):
			# Ok, at this stage we're queued. The manifest reader will
			# queue up more jobs for us as we go along.
			callback(root_job_id)

		def on_root_job_added(root_job_id):
			def on_mini_manifest(manifest_reader_job_id):
				on_manifest_reader_added(root_job_id, manifest_reader_job_id)

			# Make a manifest reader job as a child of this root job.
			configuration.job_manager.add_job(
				'paasmaker.job.prepare.manifestreader',
				{},
				"Manifest reader",
				on_mini_manifest,
				parent=root_job_id
			)

		configuration.job_manager.add_job(
			'paasmaker.job.prepare.root',
			{},
			"Prepare source for %s" % name,
			on_root_job_added,
			context=context,
			tags=tags
		)

	def start_job(self, context):
		# In the context should be a 'package' attribute. Record and in future upload this.
		self.logger.info("Finalising package for %s" % context['application_name'])

		# TODO: Use subclasses of this to handle storage on S3, shared filesystems, etc.
		# For now... store it in the path we've been supplied, and make the URL to it a Paasmaker URL.
		session = self.configuration.get_database_session()
		version = session.query(paasmaker.model.ApplicationVersion).get(context['application_version_id'])

		# Set the source path.
		# Only store the package name, not the leading path.
		package_name = os.path.basename(context['package'])
		version.source_path = "paasmaker://%s/%s" % (self.configuration.get_node_uuid(), package_name)

		# Calculate the checksum of this source package.
		checksum = paasmaker.util.streamingchecksum.StreamingChecksum(
			context['package'],
			self.configuration.io_loop,
			self.logger
		)

		def checksum_complete(checksum):
			version.source_checksum = checksum
			version.state = constants.VERSION.PREPARED
			session.add(version)
			session.commit()

			self.success({}, "Successfully prepared package for %s" % context['application_name'])

		checksum.start(checksum_complete)

	# TODO: Can't place versions into ERROR state when they can't be prepared. Fix this!

class PrepareJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(PrepareJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(PrepareJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def on_job_catchall(self, message):
		# This is for debugging.
		#print str(message.flatten())
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
		workspace.stub = 'work'
		s.add(workspace)
		s.commit()

		ApplicationPrepareRootJob.setup(
			self.configuration,
			'foo.com',
			manifest,
			workspace.id,
			self.stop,
			uploaded_file=tempzip
		)

		root_job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')

		# And make it work.
		self.configuration.job_manager.allow_execution(root_job_id, self.stop)
		self.wait()

		result = self.wait()
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		#print
		#self.dump_job_tree(root_job_id)
		#self.wait()

		self.configuration.job_manager.get_context(root_job_id, self.stop)
		context = self.wait()

		# Verify the package exists, and has the files we expect.
		self.assertTrue(os.path.exists(context['package']), "Packed file does not exist.")
		files = subprocess.check_output(['tar', 'ztvf', context['package']])
		self.assertIn("app.py", files, "Can't find app.py.")
		self.assertIn("manifest.yml", files, "Can't find manifest.")
		self.assertIn("prepare.txt", files, "Can't find prepare.txt - prepare probably failed.")
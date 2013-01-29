
import os
import subprocess
import json

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class ApplicationPrepareRootJob(BaseJob):
	@staticmethod
	def setup(configuration,
			name,
			manifest_path,
			workspace_id,
			scm_name,
			scm_parameters,
			callback,
			application_id=None):
		# Set up the context.
		context = {}
		context['manifest_path'] = manifest_path
		context['application_name'] = name
		context['workspace_id'] = workspace_id
		context['application_id'] = application_id
		context['scm_name'] = scm_name
		context['scm_parameters'] = scm_parameters
		context['environment'] = {}

		tags = []
		tags.append('workspace:%d' % workspace_id)

		# The root of this tree.
		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.prepare.root',
			{},
			"Prepare source for %s" % name,
			context=context,
			tags=tags
		)

		manifestreader = tree.add_child()
		manifestreader.set_job(
			'paasmaker.job.prepare.manifestreader',
			{},
			"Manifest reader",
		)

		scm = manifestreader.add_child()
		scm.set_job(
			'paasmaker.job.prepare.scm',
			{
				'scm_name': scm_name,
				'scm_parameters': scm_parameters
			},
			'SCM export'
		)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added)

	def start_job(self, context):
		# In the context should be a 'package' attribute. Record and in future upload this.
		self.logger.info("Finalising package for %s" % context['application_name'])

		# TODO: Use subclasses of this to handle storage on S3, shared filesystems, etc.
		# For now... store it in the path we've been supplied, and make the URL to it a Paasmaker URL.
		session = self.configuration.get_database_session()
		version = session.query(paasmaker.model.ApplicationVersion).get(context['application_version_id'])

		# Set the source path.
		# Only store the package name, not the leading path.
		version.checksum = context['package_checksum']
		version.source_package_type = context['package_type']

		def store_complete(url, message):
			self.logger.info(message)
			version.source_path = url
			version.state = constants.VERSION.PREPARED
			session.add(version)
			session.commit()

			self.success({}, "Successfully prepared package for %s" % context['application_name'])

		def store_failed(message, exception=None):
			# Handle a failed store.
			self.logger.error(message)
			if exception:
				self.logger.error("Exception", exc_info=exception)
			self.failed(message)
			# end of pack_failed()

		# Store the package.
		# Locate a suitable plugin to do this.
		storer_plugin_name = 'paasmaker.storer.default'
		if 'preferred_storer' in context:
			storer_plugin_name = 'paasmaker.storer.%s' % context['preferred_storer']

		plugin_exists = self.configuration.plugins.exists(
			storer_plugin_name,
			paasmaker.util.plugin.MODE.STORER
		)

		if not plugin_exists:
			if 'preferred_storer' in context:
				error_message = "The preferred storer %s was not found." % storer_plugin_name
			else:
				error_message = "Your Paasmaker configuration is incomplete. No default source storer plugin is configured."

			self.logger.error(error_message)
			self.failed(error_message)
			return

		storer_plugin = self.configuration.plugins.instantiate(
			storer_plugin_name,
			paasmaker.util.plugin.MODE.STORER,
			{},
			self.logger
		)

		storer_plugin.store(context['package_file'], context['package_checksum'], context['package_type'], store_complete, store_failed)

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
			'paasmaker.scm.zip',
			{
				'location': tempzip
			},
			self.stop
		)

		root_job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')

		# And make it work.
		self.configuration.job_manager.allow_execution(root_job_id, self.stop)
		self.wait()

		#self.configuration.job_manager.get_pretty_tree(root_job_id, self.stop)
		#tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

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
		self.assertTrue(os.path.exists(context['package_file']), "Packed file does not exist.")
		files = subprocess.check_output(['tar', 'ztvf', context['package_file']])
		self.assertIn("app.py", files, "Can't find app.py.")
		self.assertIn("manifest.yml", files, "Can't find manifest.")
		self.assertIn("prepare.txt", files, "Can't find prepare.txt - prepare probably failed.")
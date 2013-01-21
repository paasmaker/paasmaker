
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE
from ...testhelpers import TestHelpers

import logging

import tornado
from pubsub import pub

import colander

# Root job: actual application delete (deletes the objects in the db)
# - service distributor: create jobs under the root for deleting each service
# - service a
# - service b
#
# Things this job doesn't do:
# - clean up packed files and source code. For now, leave this to a cleanup task
# - log files will expire eventually anyway
# - jobs will also expire
# - routing table will have already been dumped (because all instances have stopped before deletion)
# - routing stats: there's not yet a good way to export them


class ApplicationDeleteJobParametersSchema(colander.MappingSchema):
	application_id = colander.SchemaNode(
		colander.Integer(),
		title="Application ID",
		description="ID of the application to be deleted"
	)

class ApplicationDeleteRootJob(BaseJob):
	MODES = {
		MODE.JOB: ApplicationDeleteJobParametersSchema()
	}

	def start_job(self, context):
		session = self.configuration.get_database_session()
		application = session.query(
			paasmaker.model.Application
		).get(
			self.parameters["application_id"]
		)
		
		if application is None:
			error_msg = "Can't find application of id %d to delete" % self.parameters["application_id"]
			self.logger.error(error_msg)
			self.failed(error_msg)
			return
		
		session.delete(application)
		session.commit()
		
		self.success({}, "Deleted application id %d" % self.parameters["application_id"])

	@classmethod
	def setup_for_application(cls, configuration, application, callback):
		tags = [
			'workspace:%d' % application.workspace.id,
			'application:%d' % application.id
		]

		configuration.job_manager.add_job(
			'paasmaker.job.application.delete',
			{
				'application_id': application.id
			},
			"Delete application %s" % application.name,
			callback=callback,
			tags=tags
		)

class ApplicationDeleteJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ApplicationDeleteJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(ApplicationDeleteJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_simple(self):
		session = self.configuration.get_database_session()

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		session.add(application)
		session.commit()

		ApplicationDeleteRootJob.setup_for_application(
			self.configuration,
			application,
			self.stop
		)

		root_job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(root_job_id, self.stop)
		self.wait()
	
		result = self.wait()
		while result.state not in (constants.JOB_FINISHED_STATES):
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Application delete job did not succeed")

		session.close()
		session = self.configuration.get_database_session()

		shouldnt_exist = session.query(
			paasmaker.model.Application
		).get(
			application.id
		)

		self.assertIsNone(shouldnt_exist, "Application appears to still exist after being deleted")
		
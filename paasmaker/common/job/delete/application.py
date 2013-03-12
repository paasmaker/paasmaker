
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
	"""
	A job to delete an application.
	"""
	MODES = {
		MODE.JOB: ApplicationDeleteJobParametersSchema()
	}

	def start_job(self, context):
		def got_session(session):
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
			session.close()

			self.success({}, "Deleted application id %d" % self.parameters["application_id"])

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

	@classmethod
	def setup_for_application(cls, configuration, application, callback):
		tags = [
			'workspace:%d' % application.workspace.id,
			'application:%d' % application.id
		]

		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.application.delete',
			{
				'application_id': application.id
			},
			"Delete application %s" % application.name,
			tags=tags
		)

		for service in application.services:
			servicejob = tree.add_child()
			servicejob.set_job(
				'paasmaker.job.application.delete.service',
				{
					'service_id': service.id
				},
				"Delete service '%s'" % service.name
			)

		def on_tree_added(root_id):
			callback(root_id)

		# Add that entire tree into the job manager.
		configuration.job_manager.add_tree(tree, on_tree_added)

class ApplicationDeleteServiceParametersSchema(colander.MappingSchema):
	service_id = colander.SchemaNode(
		colander.Integer(),
		title="Service ID",
		description="ID of the service to be deleted"
	)

class ApplicationDeleteServiceJob(BaseJob):
	"""
	A job to delete a service that an application uses.
	"""
	MODES = {
		MODE.JOB: ApplicationDeleteServiceParametersSchema()
	}

	def start_job(self, context):
		def got_session(session):
			self.session = session
			self.service = self.session.query(
				paasmaker.model.Service
			).get(
				self.parameters['service_id']
			)

			plugin_exists = self.configuration.plugins.exists(
				self.service.provider,
				paasmaker.util.plugin.MODE.SERVICE_DELETE
			)

			if not plugin_exists:
				self.service.state = constants.SERVICE.ERROR
				self.session.add(self.service)
				self.session.commit()
				self.session.close()
				self.failed("Plugin with mode SERVICE_DELETE doesn't exist for service %s" %self.service.provider)
				return

			service_plugin = self.configuration.plugins.instantiate(
				self.service.provider,
				paasmaker.util.plugin.MODE.SERVICE_DELETE,
				self.service.parameters,
				self.logger
			)

			service_plugin.remove(self.service.name, self.service.credentials, self._service_success, self._service_failure)

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

	def _service_success(self, message):
		self.logger.info(message)
		self.session.refresh(self.service)

		self.session.delete(self.service)
		self.session.commit()
		self.session.close()

		# And signal completion.
		self.success({}, "Successfully deleted service %s" % self.service.name)

	def _service_failure(self, message, exception=None):
		# Record the new state.
		self.session.refresh(self.service)
		self.service.state = constants.SERVICE.ERROR
		self.session.add(self.service)
		self.session.commit()
		self.session.close()

		if exception:
			self.logger.error("Exception", exc_info=exception)

		# Signal failure.
		self.failed(message)

class ApplicationDeleteJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ApplicationDeleteJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

		self.configuration.plugins.register(
			'paasmaker.service.parameters',
			'paasmaker.pacemaker.service.parameters.ParametersService',
			{},
			'Parameters Service'
		)


	def tearDown(self):
		self.configuration.cleanup()
		super(ApplicationDeleteJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def test_simple(self):
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		service = paasmaker.model.Service()
		service.application = application
		service.name = 'test1'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

		service = paasmaker.model.Service()
		service.application = application
		service.name = 'test2'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

		service = paasmaker.model.Service()
		service.application = application
		service.name = 'test3'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

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
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()

		shouldnt_exist = session.query(
			paasmaker.model.Application
		).get(
			application.id
		)

		self.assertIsNone(shouldnt_exist, "Application appears to still exist after being deleted")

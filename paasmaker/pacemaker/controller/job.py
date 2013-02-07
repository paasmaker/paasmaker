import logging
import json

import paasmaker
from paasmaker.common.controller.base import BaseController, BaseControllerTest, BaseWebsocketHandler, WebsocketLongpollWrapper
from paasmaker.common.core import constants

from pubsub import pub
import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_workspace(self, workspace_id):
		workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
		if not workspace:
			raise tornado.web.HTTPError(404, "No such workspace.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)
		return workspace

	def _get_application(self, application_id):
		application = self.db().query(paasmaker.model.Application).get(int(application_id))
		if not application:
			raise tornado.web.HTTPError(404, "No such application.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=application.workspace)
		return application

	def _get_version(self, version_id):
		version = self.db().query(paasmaker.model.ApplicationVersion).get(int(version_id))
		if not version:
			raise tornado.web.HTTPError(404, "No such version.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=version.application.workspace)
		return version

	def _get_instance_type(self, instance_type_id):
		instance_type = self.db().query(paasmaker.model.ApplicationInstanceType).get(int(instance_type_id))
		if not instance_type:
			raise tornado.web.HTTPError(404, "No such instance type.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=instance_type.application_version.application.workspace)
		return instance_type

	@tornado.web.asynchronous
	def get(self, job_list_type, input_id=None):
		tag = None
		job_list = None
		ret = None
		sub_type = ""
		if self.raw_params.has_key('sub'):
			sub_type = self.raw_params['sub'] + ':'
		if job_list_type == 'workspace':
			workspace = self._get_workspace(input_id)
			name = "Workspace %s" % workspace.name
			ret = "/workspace/%d/applications" % workspace.id
			ret_name = name
			tag = "workspace:%s%d" % (sub_type, workspace.id)
		elif job_list_type == 'application':
			application = self._get_application(input_id)
			name = "Application %s" % application.name
			ret = "/application/%d" % application.id
			ret_name = name
			tag = "application:%s%d" % (sub_type, application.id)
		elif job_list_type == 'version':
			version = self._get_version(input_id)
			name = "Version %d of %s" % (version.version, version.application.name)
			ret = "/version/%d" % version.id
			ret_name = name
			tag = "application_version:%s%d" % (sub_type, version.id)
		elif job_list_type == 'health':
			# You must have HEALTH_CHECK permission.
			self.require_permission(constants.PERMISSION.HEALTH_CHECK)

			# Ignore the argument.
			tag = "health"
			if len(sub_type) > 0:
				tag += ":" + sub_type[0:-1]
			name = "Health Checks"
			ret = None
			ret_name = None
		elif job_list_type == 'periodic':
			# You must have SYSTEM_ADMINISTRATION permission.
			self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

			# Ignore the argument.
			tag = "periodic"
			if len(sub_type) > 0:
				tag += ":" + sub_type[0:-1]
			name = "Periodic Tasks"
			ret = None
			ret_name = None
		elif job_list_type == 'instancetype':
			instance_type = self._get_instance_type(input_id)
			name = "Instance type %s of %s version %d" % (
				instance_type.name,
				instance_type.application_version.application.name,
				instance_type.application_version.version
			)
			ret = "/version/%d" % instance_type.application_version.id
			ret_name = name
			tag = "application_instance_type:%s%d" % (sub_type, instance_type.id)
		elif job_list_type == 'detail':
			# TODO: We're not checking permissions here. But the theory is that
			# the job ID will be hard to guess. Revisit this at a later date.
			job_list = [input_id]
			name = "Detail for job"
			ret_name = "previous"

		# Optional return URL.
		if self.raw_params.has_key('ret'):
			ret = self.raw_params['ret']
			ret_name = "previous"

		self.add_data_template('name', name)
		self.add_data_template('ret', ret)
		self.add_data_template('ret_name', ret_name)

		# TODO: Paginate...
		# TODO: Unit test.
		def on_found_jobs(job_ids):
			self.add_data('jobs', job_ids)
			self.render("job/list.html")

		def on_found_tree(tree):
			self.add_data('detail', tree)
			on_found_jobs(job_list)

		if tag:
			# Search by tag.
			self.configuration.job_manager.find_by_tag(tag, on_found_jobs, limit=50)
		else:
			# Use the single given ID. Attach the current state to this
			# page as well...
			self.configuration.job_manager.get_pretty_tree(input_id, on_found_tree)

	@staticmethod
	def get_routes(configuration):
		routes = []
		# The route for, eg, /job/list/workspace/1
		routes.append((r"/job/list/(workspace|application|version|instancetype)/(\d+)", JobListController, configuration))
		routes.append((r"/job/list/(health|periodic)", JobListController, configuration))
		# The route for job detail. Eg, /job/detail/<jobid>
		routes.append((r"/job/(detail)/([-\w\d]+)", JobListController, configuration))
		return routes

class JobAbortController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self, job_id):
		# TODO: Attempt to tie this to a workspace for permissions
		# purposes.
		self.require_permission('JOB_ABORT')
		self.configuration.job_manager.abort(job_id)
		self.add_data('job_id', job_id)
		self.render("job/abort.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/job/abort/(.*)", JobAbortController, configuration))
		return routes

class JobSubscribeSchema(colander.MappingSchema):
	job_id = colander.SchemaNode(colander.String(),
		title="Job ID",
		description="The ID of the job to start monitoring.")
class JobUnSubscribeSchema(colander.MappingSchema):
	job_id = colander.SchemaNode(colander.String(),
		title="Job ID",
		description="The ID of the job to stop monitoring.")
class JobTreeSchema(JobSubscribeSchema):
	pass

class JobStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.NODE, BaseWebsocketHandler.USER, BaseWebsocketHandler.SUPER]

	def open(self):
		self.subscribed = {}
		pub.subscribe(self.on_job_status, 'job.status')

	def on_job_status(self, message):
		job_id = message.job_id
		if self.subscribed.has_key(job_id):
			def got_job_full(jobs):
				self.send_success('status', jobs[job_id])

			# Fetch all the data.
			self.configuration.job_manager.get_jobs([message.job_id], got_job_full)

		parent_id = message.parent_id
		if parent_id and self.subscribed.has_key(parent_id):
			# Send a new job.
			def on_got_job(data):
				self.send_success('new', data[job_id])
			self.configuration.job_manager.get_jobs([job_id], on_got_job)
			self.subscribed[message.job_id] = True

	def on_message(self, message):
		# Message should be JSON.
		parsed = self.parse_message(message)
		if parsed:
			if parsed['request'] == 'subscribe':
				self.handle_subscribe(parsed)
			if parsed['request'] == 'unsubscribe':
				self.handle_unsubscribe(parsed)
			if parsed['request'] == 'tree':
				self.handle_tree(parsed)

	def handle_subscribe(self, message):
		# Must match the subscribe schema.
		subscribe = self.validate_data(message, JobSubscribeSchema())
		if subscribe:
			# Subscribe to everything in the tree.
			self.configuration.job_manager.get_pretty_tree(subscribe['job_id'], self.got_pretty_tree)
			self.configuration.job_manager.get_flat_tree(subscribe['job_id'], self.got_flat_tree_subscribe)

	def handle_tree(self, message):
		# Must match the subscribe schema.
		tree = self.validate_data(message, JobTreeSchema())
		if subscribe:
			# Subscribe to everything in the tree.
			self.configuration.job_manager.get_pretty_tree(tree['job_id'], self.got_pretty_tree)

	def got_pretty_tree(self, tree):
		# Send back the pretty tree to the client.
		self.send_success('tree', tree)

	def got_flat_tree_subscribe(self, job_ids):
		# Subscribe to all of the IDs that came back.
		for job_id in job_ids:
			self.subscribed[job_id] = True
		self.send_success('subscribed', job_ids)

	def handle_unsubscribe(self, message):
		# Must match the unsubscribe schema.
		unsubscribe = self.validate_data(message, LogUnSubscribeSchema())
		if unsubscribe:
			self.configuration.job_manager.get_flat_tree(unsubscribe['job_id'], self.got_flat_tree_unsubscribe)

	def got_flat_tree_unsubscribe(self, job_ids):
		for job_id in job_ids:
			self.configuration.get_job_watcher().remove_watch(job_id)
			pub.unsubscribe(self.job_message_update, self.configuration.get_job_message_pub_topic(job_id))
			del self.subscribed[job_id]
		self.send_success('unsubscribed', job_ids)

	def on_close(self):
		pub.unsubscribe(self.on_job_status, 'job.status')

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/job/stream", JobStreamHandler, configuration))
		return routes

class JobStreamHandlerTestClient(paasmaker.thirdparty.twc.websocket.WebSocket):
	def on_open(self):
		self.messages = []

	def subscribe(self, job_id):
		data = {'job_id': job_id}
		auth = self.configuration.get_flat('node_token')
		message = {'request': 'subscribe', 'data': data, 'auth': auth}
		self.write_message(json.dumps(message))

	def on_message(self, m):
		parsed = json.loads(m)
		self.messages.append(parsed)

class JobStreamHandlerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = JobStreamHandler.get_routes({'configuration': self.configuration})
		routes.extend(WebsocketLongpollWrapper.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def setUp(self):
		# Call the parent setup...
		super(JobStreamHandlerTest, self).setUp()

		# Register sample jobs.
		self.configuration.plugins.register(
			'paasmaker.job.success',
			'paasmaker.common.job.manager.manager.TestSuccessJobRunner',
			{},
			'Test Success Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.failure',
			'paasmaker.common.job.manager.manager.TestFailJobRunner',
			{},
			'Test Fail Job'
		)
		self.configuration.plugins.register(
			'paasmaker.job.aborted',
			'paasmaker.common.job.manager.manager.TestAbortJobRunner',
			{},
			'Test Abort Job'
		)

		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()

	def test_job_stream(self):
		client = JobStreamHandlerTestClient("ws://localhost:%d/job/stream" % self.get_http_port(), io_loop=self.io_loop)
		client.configuration = self.configuration
		self.short_wait_hack()

		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()

		client.subscribe(root_id)

		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id, tags=['test'])
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		#print json.dumps(client.messages, indent=4, sort_keys=True)

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		# Wait for it all to complete.
		self.short_wait_hack(length=0.4)

		#print json.dumps(client.messages, indent=4, sort_keys=True)

		# Now, analyze what happened.
		# TODO: Make this clearer and more exhaustive.
		expected_types = [
			'subscribed',
			'status',
			'new',
			'tree',
			'new',
			'new',
			'status',
			'status',
			'status',
			'status',
			'status'
		]

		self.assertEquals(len(expected_types), len(client.messages), "Not the right number of messages.")
		for i in range(len(expected_types)):
			self.assertEquals(client.messages[i]['type'], expected_types[i], "Wrong type for message %d" % i)

	def test_job_stream_longpoll(self):

		self.manager.add_job('paasmaker.job.success', {}, "Example root job.", self.stop)
		root_id = self.wait()

		messages = []

		def on_message(message):
			messages.append(message)

		def on_error(error):
			print error

		remote_request = paasmaker.common.api.job.JobStreamAPIRequest(self.configuration)
		remote_request.set_superkey_auth()
		remote_request.set_callbacks(on_message, on_error)
		remote_request.set_stream_mode('longpoll')
		remote_request.subscribe(root_id)

		self.manager.add_job('paasmaker.job.success', {}, "Example sub1 job.", self.stop, parent=root_id, tags=['test'])
		sub1_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example sub2 job.", self.stop, parent=root_id)
		sub2_id = self.wait()
		self.manager.add_job('paasmaker.job.success', {}, "Example subsub1 job.", self.stop, parent=sub1_id)
		subsub1_id = self.wait()

		#print json.dumps(messages, indent=4, sort_keys=True)

		# Start processing them.
		self.manager.allow_execution(root_id, callback=self.stop)
		self.wait()

		# Wait for it all to complete.
		self.short_wait_hack(length=0.4)

		#print json.dumps(messages, indent=4, sort_keys=True)

		# Now, analyze what happened.
		# TODO: Make this clearer and more exhaustive.
		expected_types = [
			'subscribed',
			'status',
			'new',
			'tree',
			'new',
			'new',
			'status',
			'status',
			'status',
			'status',
			'status'
		]

		self.assertEquals(len(expected_types), len(messages), "Not the right number of messages.")
		for i in range(len(expected_types)):
			self.assertEquals(messages[i]['type'], expected_types[i], "Wrong type for message %d" % i)

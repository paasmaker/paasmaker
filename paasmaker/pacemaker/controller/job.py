import logging
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest, BaseWebsocketHandler
from paasmaker.common.core import constants

from pubsub import pub
import tornado
import tornado.testing
import colander
from ws4py.client.tornadoclient import TornadoWebSocketClient

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_workspace(self, workspace_id):
		workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
		if not workspace:
			raise tornado.web.HTTPError(404, "No such workspace.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)
		return workspace

	@tornado.web.asynchronous
	def get(self, workspace_id):
		workspace = self._get_workspace(workspace_id)
		self.add_data('workspace', workspace)

		# TODO: Paginate...
		# TODO: Unit test.
		def on_found_jobs(job_ids):
			self.add_data('jobs', job_ids)
			self.render("job/list.html")

		self.configuration.job_manager.find_by_tag('workspace:%d' % workspace.id, on_found_jobs, limit=10)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/job/(\d+)/list", JobController, configuration))
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
				# Send the status.
				self.send_success('status', message.flatten())

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

class JobStreamHandlerTestClient(TornadoWebSocketClient):
	def opened(self):
		self.messages = []

	def closed(self, code, reason=None):
		#print "Client: closed"
		pass

	def subscribe(self, job_id):
		data = {'job_id': job_id}
		auth = {'method': 'node', 'value': self.configuration.get_flat('node_token')}
		message = {'request': 'subscribe', 'data': data, 'auth': auth}
		self.send(json.dumps(message))

	def received_message(self, m):
		#print "Client: got %s" % m
		# Record the log lines.
		# CAUTION: m is NOT A STRING.
		parsed = json.loads(str(m))
		self.messages.append(parsed)

class JobStreamHandlerTest(BaseControllerTest):
	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = JobStreamHandler.get_routes({'configuration': self.configuration})
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
		client.connect()
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
		self.short_wait_hack(length=0.2)

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
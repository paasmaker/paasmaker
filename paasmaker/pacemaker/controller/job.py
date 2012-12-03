import logging

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest, BaseWebsocketHandler
from paasmaker.common.core import constants

from pubsub import pub
import tornado
import tornado.testing
import colander

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
		def on_found_jobs_summary(jobs):
			print str(jobs)
			self.add_data('jobs', jobs)
			self.render("job/list.html")

		def on_found_jobs(job_ids):
			self.configuration.job_manager.get_jobs(job_ids, on_found_jobs_summary)

		self.configuration.job_manager.find_by_tag('workspace:%d' % workspace.id, on_found_jobs)

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

class JobStreamHandler(BaseWebsocketHandler):
	AUTH_METHODS = [BaseWebsocketHandler.NODE, BaseWebsocketHandler.USER]

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
						self.send_success('new', data[0])
				self.configuration.job_manager.get_jobs([job_id], on_got_job)

	def on_message(self, message):
		# Message should be JSON.
		print str(self.request)
		parsed = self.parse_message(message)
		if parsed:
			if parsed['request'] == 'subscribe':
				self.handle_subscribe(parsed)
			if parsed['request'] == 'unsubscribe':
				self.handle_unsubscribe(parsed)

	def handle_subscribe(self, message):
		# Must match the subscribe schema.
		subscribe = self.validate_data(message, JobSubscribeSchema())
		if subscribe:
			# Subscribe to everything in the tree.
			self.configuration.job_manager.get_pretty_tree(subscribe['job_id'], self.got_pretty_tree)
			self.configuration.job_manager.get_flat_tree(subscribe['job_id'], self.got_flat_tree_subscribe)

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
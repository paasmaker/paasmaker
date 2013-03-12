import logging
import json
import unittest

import paasmaker
from paasmaker.common.controller.base import BaseController, BaseControllerTest
from paasmaker.common.core import constants

from pubsub import pub
import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JobListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	@tornado.gen.engine
	def _get_workspace(self, workspace_id, callback):
		session = yield tornado.gen.Task(self.db)
		workspace = session.query(paasmaker.model.Workspace).get(int(workspace_id))
		if not workspace:
			raise tornado.web.HTTPError(404, "No such workspace.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=workspace)
		callback(workspace)

	@tornado.gen.engine
	def _get_application(self, application_id, callback):
		session = yield tornado.gen.Task(self.db)
		application = session.query(paasmaker.model.Application).get(int(application_id))
		if not application:
			raise tornado.web.HTTPError(404, "No such application.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=application.workspace)
		callback(application)

	@tornado.gen.engine
	def _get_version(self, version_id, callback):
		session = yield tornado.gen.Task(self.db)
		version = session.query(paasmaker.model.ApplicationVersion).get(int(version_id))
		if not version:
			raise tornado.web.HTTPError(404, "No such version.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=version.application.workspace)
		callback(version)

	@tornado.gen.engine
	def _get_instance_type(self, instance_type_id, callback):
		session = yield tornado.gen.Task(self.db)
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(int(instance_type_id))
		if not instance_type:
			raise tornado.web.HTTPError(404, "No such instance type.")
		self.require_permission(constants.PERMISSION.WORKSPACE_VIEW, workspace=instance_type.application_version.application.workspace)
		callback(instance_type)

	@tornado.gen.engine
	def get(self, job_list_type, input_id=None):
		tag = None
		job_list = None
		ret = None
		sub_type = ""
		if self.raw_params.has_key('sub'):
			sub_type = self.raw_params['sub'] + ':'
		if job_list_type == 'workspace':
			workspace = yield tornado.gen.Task(self._get_workspace, input_id)
			name = "Workspace %s" % workspace.name
			ret = "/workspace/%d/applications" % workspace.id
			ret_name = name
			tag = "workspace:%s%d" % (sub_type, workspace.id)
		elif job_list_type == 'application':
			application = yield tornado.gen.Task(self._get_application, input_id)
			name = "Application %s" % application.name
			ret = "/application/%d" % application.id
			ret_name = name
			tag = "application:%s%d" % (sub_type, application.id)
		elif job_list_type == 'version':
			version = yield tornado.gen.Task(self._get_version, input_id)
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
			instance_type = yield tornado.gen.Task(self._get_instance_type, input_id)
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

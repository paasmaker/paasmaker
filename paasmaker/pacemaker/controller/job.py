import logging

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

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
			self.finish()

		def on_found_jobs(job_ids):
			self.configuration.job_manager.get_jobs(job_ids, on_found_jobs_summary)

		self.configuration.job_manager.find_by_tag('workspace:%d' % workspace.id, on_found_jobs)

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/job/(\d+)/list", JobController, configuration))
		return routes

import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado
from sqlalchemy import func

class OverviewController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	@tornado.web.asynchronous
	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_OVERVIEW)

		# Instance status counts
		instance_status_counts = self.db().query(
			paasmaker.model.ApplicationInstance.state,
			func.count()
		).group_by(
			paasmaker.model.ApplicationInstance.state
		)
		self.add_data('instances', instance_status_counts)

		node_status_counts = self.db().query(
			paasmaker.model.Node.state,
			func.count()
		).group_by(
			paasmaker.model.Node.state
		)
		self.add_data('nodes', node_status_counts)

		# Workspace routing stats.
		self.workspace_list = self.db().query(
			paasmaker.model.Workspace
		).order_by(
			paasmaker.model.Workspace.name.asc()
		).all()
		self.add_data_template('workspaces', list(self.workspace_list))
		self.workspace_list.reverse()

		self._process_workspace()

	def _process_workspace(self, stats=None):
		try:
			workspace = self.workspace_list.pop()
			self._get_router_stats_for(
				'workspace',
				workspace.id,
				self._process_workspace,
				output_key="workspace_%d_router" % workspace.id,
				title="Workspace %s" % workspace.name
			)

		except IndexError, ex:
			self._done_workspaces()

	def _done_workspaces(self):
		self._get_router_stats_for('uncaught', 0, self._done_uncaught, title="Uncaught Requests")

	def _done_uncaught(self, result):
		self._get_router_stats_for('pacemaker', 0, self._done, title="Pacemaker Requests", output_key="pacemaker")

	def _done(self, result):
		self.render("overview.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/overview", OverviewController, configuration))
		return routes


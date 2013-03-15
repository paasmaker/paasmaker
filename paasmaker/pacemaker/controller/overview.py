
import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado
from sqlalchemy import func

class OverviewController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	@tornado.gen.engine
	def get(self):
		self.require_permission(constants.PERMISSION.SYSTEM_OVERVIEW)

		# Instance status counts
		instance_status_counts = self.session.query(
			paasmaker.model.ApplicationInstance.state,
			func.count()
		).group_by(
			paasmaker.model.ApplicationInstance.state
		)
		self.add_data('instances', instance_status_counts)

		node_status_counts = self.session.query(
			paasmaker.model.Node.state,
			func.count()
		).group_by(
			paasmaker.model.Node.state
		)
		self.add_data('nodes', node_status_counts)

		# Workspace routing stats.
		self.workspace_list = self.session.query(
			paasmaker.model.Workspace
		).order_by(
			paasmaker.model.Workspace.name.asc()
		).all()
		self.add_data_template('workspaces', list(self.workspace_list))

		self.render("overview.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/overview", OverviewController, configuration))
		return routes


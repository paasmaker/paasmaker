
import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado
from sqlalchemy import func

class IndexController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		if self.configuration.is_pacemaker():
			if self.user and self.has_permission(constants.PERMISSION.SYSTEM_OVERVIEW):
				self.show_overview()
			else:
				self.redirect('/login')
		else:
			self.render("index-notpacemaker.html")

	@tornado.gen.engine
	def show_overview(self):
		# self.require_permission(constants.PERMISSION.SYSTEM_OVERVIEW)

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

		# Generate a quick link list of 5 applications;
		# TODO: sort by recentness of version deployed,
		# or some other freshness measure
		self.application_list = self.session.query(
			paasmaker.model.Application
		).order_by(
			paasmaker.model.Application.name.asc()
		).limit(5).all()
		self.add_data_template('applications', list(self.application_list))
		
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
		routes.append((r"/", IndexController, configuration))
		return routes


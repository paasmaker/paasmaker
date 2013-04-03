#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker
from paasmaker.common.controller import BaseController
from paasmaker.common.core import constants

import tornado
from sqlalchemy import func

class IndexController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		if self.configuration.is_pacemaker():
			if self.get_current_user():
				if self.has_permission(constants.PERMISSION.SYSTEM_OVERVIEW):
					self.show_overview()
				else:
					self.render("overview-blank.html")
			else:
				self.redirect("/login")
		else:
			self.render("index-notpacemaker.html")

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

		# Workspace list. Based on permissions.
		workspace_list = self._my_workspace_list()
		self.add_data_template('workspaces', workspace_list)

		# Generate a quick link list of 5 applications;
		# TODO: sort by recentness of version deployed,
		# or some other freshness measure
		my_workspace_idset = self._my_workspace_list(idset=True)
		application_list = self.session.query(
			paasmaker.model.Application
		).filter(
			paasmaker.model.Application.workspace_id.in_(my_workspace_idset)
		).order_by(
			paasmaker.model.Application.name.asc()
		).limit(5)
		self.add_data_template('applications', application_list)

		self.render("overview.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/", IndexController, configuration))
		return routes

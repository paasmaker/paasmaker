define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var UserMetadataModel = Backbone.Model.extend({
		defaults: {
			expanded_workspaces: [],
			expanded_applications: []
		},
		url: '/profile/userdata?format=json',
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.userdata;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},
		isWorkspaceExpanded: function(workspace_id) {
			if (!this.attributes.expanded_workspaces) {
				this.attributes.expanded_workspaces = [];
			}

			return _.indexOf(this.attributes.expanded_workspaces, workspace_id) != -1;
		},
		isApplicationExpanded: function(application_id) {
			if (!this.attributes.expanded_applications) {
				this.attributes.expanded_applications = [];
			}

			return _.indexOf(this.attributes.expanded_applications, application_id) != -1;
		},
		markWorkspaceExpanded: function(workspace_id) {
			if (!this.isWorkspaceExpanded(workspace_id)) {
				this.attributes.expanded_workspaces.push(workspace_id);
				this.saveUpdates();
			}
		},
		markApplicationExpanded: function(application_id) {
			if (!this.isApplicationExpanded(application_id)) {
				this.attributes.expanded_applications.push(application_id);
				this.saveUpdates();
			}
		},
		markWorkspaceCollapsed: function(workspace_id) {
			if (this.isWorkspaceExpanded(workspace_id)) {
				if (!this.unexpand_workspace) {
					this.unexpand_workspace = [];
				}
				this.unexpand_workspace.push(workspace_id);
				this.saveUpdates();
			}
		},
		markApplicationCollapsed: function(application_id) {
			if (this.isApplicationExpanded(application_id)) {
				if (!this.unexpand_application) {
					this.unexpand_application = [];
				}
				this.unexpand_application.push(application_id);
				// this.attributes.expanded_applications = _.without(this.attributes.expanded_applications, application_id);
				this.saveUpdates();
			}
		},
		saveUpdates: function() {
			// Fetch the latest from the server, then save the updated attributes.
			// TODO: Less hackish.
			var working = {};
			working.expanded_workspaces = this.attributes.expanded_workspaces;
			working.expanded_applications = this.attributes.expanded_applications;

			var _self = this;
			this.fetch({
				success: function(model, response, options) {
					// From the server model - merge in our data.
					if (!model.attributes.expanded_workspaces) {
						model.attributes.expanded_workspaces = [];
					}
					if (!model.attributes.expanded_applications) {
						model.attributes.expanded_applications = [];
					}
					if (!_self.unexpand_workspace) {
						_self.unexpand_workspace = [];
					}
					if (!_self.unexpand_application) {
						_self.unexpand_application = [];
					}

					var resultWorkspaces = _.union(working.expanded_workspaces, model.attributes.expanded_workspaces);
					resultWorkspaces = _.difference(resultWorkspaces, _self.unexpand_workspace);
					var resultApplications = _.union(working.expanded_applications, model.attributes.expanded_applications);
					resultApplications = _.difference(resultApplications, _self.unexpand_application);

					_self.save({
						userdata: {
							expanded_workspaces: resultWorkspaces,
							expanded_applications: resultApplications
						}
					});
				}
			});
		}
	});

	return UserMetadataModel;
});
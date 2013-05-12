define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/workspace/sidebar.html',
	'tpl!templates/workspace/sidebar-entry.html',
	'tpl!templates/workspace/application-sidebar-entry.html',
	'tpl!templates/workspace/version-sidebar-entry.html'
], function($, _, Backbone, context, Bases, WorkspaceSidebarTemplate, WorkspaceEntryTemplate, ApplicationEntryTemplate, VersionEntryTemplate){
	var WorkspaceSidebarView = Bases.BaseView.extend({
		initialize: function() {
			// Render a blank template to start off with.
			this.$el.html(Bases.errorLoadingHtml + WorkspaceSidebarTemplate({workspaces: [], context: context}));

			// Add our refresh button.
			this.$('.area-controls').append($('<a href="#" class="refresh"><i class="icon-refresh"></i></a>'));

			this.activeItem = '';

			// Add all initial workspaces.
			var _self = this;
			this.collection.each(function(workspace, index, list) {
				_self.addWorkspace(workspace);
			});

			// And when the data comes in, update the whole list.
			this.collection.on('request', this.startLoadingInline, this);
			this.collection.on('sync', this.render, this);
			this.collection.on('add', this.addWorkspace, this);
			this.collection.on('change', this.changeWorkspace, this);
			this.collection.on('remove', this.removeWorkspace, this);
			this.collection.on('error', this.loadingError, this);
		},
		setActive: function(active) {
			this.activeItem = active;

			this.$('li').removeClass('active');
			if (active != '') {
				this.$('li.' + active).addClass('active');
			}
		},
		resetActive: function() {
			this.setActive(this.activeItem);
		},
		addWorkspace: function(workspace) {
			// Add a container for this workspace, and a view.
			var workspaceContainer = '<li class="divider"></li>' + WorkspaceEntryTemplate({workspace: workspace, context: context});
			var location = this.$('.workspace-sidebar-list .workspace:last');
			if (location.length == 0) {
				location = this.$('.workspace-sidebar-list .nav-header');
			}
			location.after(workspaceContainer);

			var workspaceId = workspace.id;
			var _self = this;
			workspace.applications.on('sync', function(collection, response, options) {
				options.workspace_id = workspaceId;
				_self.renderApplications(collection, response, options);
			});

			this.delegateEvents();

			if (context.usermeta.isWorkspaceExpanded(workspace.id)) {
				this.expandApplications(workspace.id);
			}
		},
		changeWorkspace: function(workspace, options) {
			var titleContainer = this.$('.workspace-' + workspace.id + ' .workspace-title');
			titleContainer.text(workspace.attributes.name);
		},
		removeWorkspace: function(workspace, collection, options) {
			this.$('.workspace-' + workspace.id).remove();
		},
		render: function() {
			this.doneLoading();
		},
		events: {
			"click a.refresh": "refreshList",
			"click a.virtual": "navigateAway",
			"click a.expand-applications": "expandApplicationsClick",
			"click a.expand-versions": "expandVersionsClick"
		},
		refreshList: function(e) {
			this.collection.fetch();
			e.preventDefault();
		},
		expandApplicationsClick: function(e) {
			e.preventDefault();
			var target = $(e.currentTarget);
			var workspaceId = target.data('workspace');
			var listElement = $('.applications', target.parent());
			if (listElement.is(':visible')) {
				listElement.slideUp();
				context.usermeta.markWorkspaceCollapsed(workspaceId);
				$('i', target).attr('class', 'icon-chevron-down');
			} else {
				listElement.slideDown();
				this.expandApplications(workspaceId);
				context.usermeta.markWorkspaceExpanded(workspaceId);
				$('i', target).attr('class', 'icon-chevron-up');
			}
		},
		expandApplications: function(workspace_id) {
			// Refresh the applications for this workspace.
			var workspace = this.collection.get(workspace_id);
			workspace.applications.fetch({workspace_id: workspace_id});
		},
		renderApplications: function(collection, response, options) {
			var applicationContainer = this.$('.workspace-' + options.workspace_id + ' .applications');
			var replacement = $('<ul class="nav nav-list applications"></ul>');
			if (context.hasPermission('APPLICATION_CREATE', options.workspace_id)) {
				replacement.append('<li class="create-application-' + options.workspace_id + '"><a class="virtual" href="/workspace/' + options.workspace_id + '/applications/new"><i class="icon-plus"></i> Create Application</a>');
			}
			collection.each(function(application, index, list) {
				replacement.append(ApplicationEntryTemplate({
					application: application,
					context: context,
					workspace_id: options.workspace_id,
					healthClasses: collection.healthClasses
				}));
			});
			if (collection.length == 0) {
				replacement.append('<li>No applications</li>');
			}
			applicationContainer.replaceWith(replacement);

			this.delegateEvents();
			this.resetActive();

			var _self = this;
			collection.each(function(application, index, list) {
				if (context.usermeta.isApplicationExpanded(application.id)) {
					_self.expandVersions(options.workspace_id, application.id);
				}
			});
		},
		expandVersionsClick: function(e) {
			e.preventDefault();
			var target = $(e.currentTarget);
			var workspaceId = target.data('workspace');
			var applicationId = target.data('application');
			var listElement = $('.versions', target.parent());
			if (listElement.is(':visible')) {
				listElement.slideUp();
				$('i', target).attr('class', 'icon-chevron-down');
				context.usermeta.markApplicationCollapsed(applicationId);
			} else {
				listElement.slideDown();
				this.expandVersions(workspaceId, applicationId);
				context.usermeta.markApplicationExpanded(applicationId);
				$('i', target).attr('class', 'icon-chevron-up');
			}
		},
		expandVersions: function(workspace_id, application_id) {
			// Refresh the applications for this workspace.
			var workspace = this.collection.get(workspace_id);
			var application = workspace.applications.get(application_id);
			application.versions.on('sync', this.renderVersions, this);
			application.versions.fetch({application_id: application_id, workspace_id: workspace_id});
		},
		renderVersions: function(collection, response, options) {
			var applicationContainer = this.$('.application-' + options.application_id + ' .versions');
			var replacement = $('<ul class="nav nav-list versions"></ul>');
			if (context.hasPermission('APPLICATION_CREATE', options.workspace_id)) {
				replacement.append('<li class="create-version-' + options.application_id + '"><a class="virtual" href="/application/' + options.application_id + '/newversion"><i class="icon-plus"></i> Create New Version</a>');
			}
			collection.each(function(version, index, list) {
				replacement.append(VersionEntryTemplate({
					version: version,
					context: context
				}));
			});
			if (collection.length == 0) {
				replacement.append('<li>No versions</li>');
			}
			applicationContainer.replaceWith(replacement);

			this.delegateEvents();
			this.resetActive();
		}
	});

	return WorkspaceSidebarView;
});
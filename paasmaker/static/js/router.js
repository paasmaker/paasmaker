define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/breadcrumb.html',
	'models/node',
	'models/user',
	'models/role',
	'models/application',
	'models/version',
	'views/node/list',
	'views/workspace/sidebar',
	'views/node/sidebar',
	'views/node/detail',
	'views/administration/sidebar',
	'views/administration/profile',
	'views/administration/list',
	'views/administration/user-list',
	'views/layout/genericloading',
	'views/administration/user-edit',
	'views/administration/role-list',
	'views/administration/role-edit',
	'views/administration/role-allocation-list',
	'views/administration/role-allocation-assign',
	'views/layout/genericjobslist',
	'views/administration/router-dump',
	'views/administration/configuration-dump',
	'views/administration/plugin-dump',
	'views/workspace/list',
	'views/application/list',
	'views/application/detail',
	'views/version/detail'
], function($, _, Backbone,
	breadcrumbTemplate,
	NodeModel,
	UserModel,
	RoleModel,
	ApplicationModel,
	VersionModel,
	NodeListView,
	WorkspaceSidebarList,
	NodeSidebarList,
	NodeDetailView,
	AdministrationSidebarList,
	ProfileView,
	AdministrationListView,
	UserListView,
	GenericLoadingView,
	UserEditView,
	RoleListView,
	RoleEditView,
	RoleAllocationListView,
	RoleAllocationAssignView,
	GenericJobsListView,
	RouterDumpView,
	ConfigurationDumpView,
	PluginsDumpView,
	WorkspaceListView,
	ApplicationListView,
	ApplicationDetailView,
	VersionDetailView
) {
	var pages = {
		workspaces: $('.page-workspaces'),
		nodes: $('.page-nodes'),
		administration: $('.page-administration'),
		'404': $('.page-404')
	};

	var sidebars = {};

	var AppRouter = Backbone.Router.extend({
		initialize: function() {
			this.route(/^$/, "overview");
			this.route('workspace/list', 'workspaceList');
			this.route(/^workspace\/(\d+)\/applications$/, 'applicationList');
			this.route(/^workspace\/(\d+)$/, 'workspaceEdit');
			this.route('workspace/create', 'workspaceEdit');

			this.route(/^application\/(\d+)$/, 'applicationView');
			this.route(/^version\/(\d+)$/, 'versionView');

			this.route('node/list', 'nodeList');
			this.route(/^node\/(\d+)$/, 'nodeDetail');

			this.route('administration/list', 'administrationList');
			this.route('profile', 'yourProfile');

			this.route('user/list', 'userList');
			this.route(/^user\/(\d+)$/, 'userEdit');
			this.route('user/create', 'userEdit');

			this.route('role/list', 'roleList');
			this.route(/^role\/(\d+)$/, 'roleEdit');
			this.route('role/create', 'roleEdit');

			this.route('role/allocation/list', 'roleAllocationList');
			this.route('role/allocation/assign', 'roleAllocationAssign');

			this.route('job/list/health', 'adminHealthJobs');
			this.route('job/list/periodic', 'adminPeriodicJobs');

			this.route('router/dump', 'adminRouterDump');
			this.route('configuration/dump', 'adminConfigurationDump');
			this.route('configuration/plugins', 'adminPluginsDump');

			// TODO: Catch the default.
			//this.route('*path', 'defaultAction');
		},

		/* HELPERS */

		ensureVisible: function(section) {
			// Get the current view to "destroy" itself.
			if (this.currentMainView) {
				this.currentMainView.destroy();
				this.currentMainView = null;
			}

			// Hide all pages.
			var _self = this;
			_.each(pages, function(value, key, list) {
				if(section != key) {
					value.hide();
				}
			});
			// Show the right page.
			_.each(pages, function(value, key, list) {
				if(section == key) {
					_self.currentPage = value;
					if (!value.is(':visible')) {
						value.fadeIn();
					}
				}
			});

			this.createSidebar(section);
		},

		createSidebar: function(section) {
			if(!sidebars[section]) {
				if(section == 'nodes') {
					sidebars[section] = new NodeSidebarList({
						collection: this.context.nodes,
						el: $('.sidebar', this.currentPage)
					});

					// Load the initial set of nodes.
					this.context.nodes.fetch();
				}
				if(section == 'workspaces') {
					sidebars[section] = new WorkspaceSidebarList({
						collection: this.context.workspaces,
						el: $('.sidebar', this.currentPage)
					});
				}
				if(section == 'administration') {
					sidebars[section] = new AdministrationSidebarList({
						collection: this.context.administrations,
						el: $('.sidebar', this.currentPage)
					});
				}
			}
		},

		breadcrumbs: function(crumbs) {
			var container = $('ul.breadcrumb', this.currentPage);
			container.html(breadcrumbTemplate({crumbs: crumbs}));
			var _self = this;
			$('a', container).click(function(e) {
				_self.context.navigate($(e.currentTarget).attr('href'));
				return false;
			});
		},

		adminSetActive: function(override) {
			var path = window.location.pathname;
			if (override) {
				path = override;
			}
			// Mark us as active.
			this.context.administrations.invoke('set', {active: false});
			this.context.administrations.findWhere({path: path}).set({active: true});
		},

		genericJobsListPage: function(sourceUrl, title) {
			this.currentMainView = new GenericJobsListView({
				url: sourceUrl,
				title: title,
				el: $('.mainarea', this.currentPage)
			});
		},

		genericDataTemplatePage: function(url, view) {
			this.currentMainView = new view({
				el: $('.mainarea', this.currentPage)
			});

			// TODO: Handle when you navigate away before this returns.
			$.ajax({
				url: url,
				dataType: 'json',
				success: _.bind(this.currentMainView.dataReady, this.currentMainView),
				error: _.bind(this.currentMainView.loadingError, this.currentMainView)
			});
		},

		/* CONTROLLER FUNCTIONS */

		overview: function() {
			this.ensureVisible('workspaces');
			console.log('Overview');
			// this.context.loadPlugin('paasmaker.service.mysql', function(mod) {
			// });
		},

		workspaceEdit: function(workspace_id) {
			this.ensureVisible('workspaces');
			console.log('Workspace edit');
			console.log(workspace_id);
		},

		workspaceList: function() {
			this.ensureVisible('workspaces');

			this.currentMainView = new WorkspaceListView({
				collection: this.context.workspaces,
				el: $('.mainarea', this.currentPage)
			});

			this.context.workspaces.fetch();

			this.breadcrumbs([{href: '/workspace/list', title: 'Workspaces'}]);

			this.currentMainView.render();
			this.currentMainView.startLoadingFull();
		},

		applicationList: function(workspace_id) {
			this.ensureVisible('workspaces');

			var _self = this;
			function applicationListInner(workspace) {
				// Add to the collection, and refetch, so it's tied
				// to the collection's events.
				_self.context.workspaces.add(workspace);
				workspace = _self.context.workspaces.get(workspace.id);

				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name}
				]);

				_self.currentMainView = new ApplicationListView({
					collection: workspace.applications,
					workspace: workspace,
					el: $('.mainarea', this.currentPage)
				});

				// Load from the server.
				workspace.applications.fetch();
			}

			// Try to load the workspace first.
			var workspace = this.context.workspaces.get(workspace_id);
			if (workspace) {
				applicationListInner(workspace);
			} else {
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', this.currentPage)});

				this.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '#', title: 'Loading ...'}
				]);

				// Load it directly from the server.
				workspace = new WorkspaceModel({'id': workspace_id});
				workspace.fetch({
					success: function(model, response, options) {
						applicationListInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			}
		},

		applicationView: function(application_id) {
			this.ensureVisible('workspaces');

			var _self = this;
			function applicationViewInner(application) {
				// Add to the collection, and refetch, so it's tied
				// to the collection's events.
				_self.context.applications.add(application);
				application = _self.context.applications.get(application.id);

				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{
						href: '/workspace/' + application.attributes.workspace.id + '/applications',
						title: application.attributes.workspace.name
					},
					{
						href: '/application/' + application.id,
						title: application.attributes.name
					}
				]);

				_self.currentMainView = new ApplicationDetailView({
					model: application,
					el: $('.mainarea', this.currentPage)
				});
			}

			// Try to load the application first.
			var application = this.context.applications.get(application_id);
			if (application) {
				applicationViewInner(application);

				// Refresh the application.
				application.fetch();
			} else {
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', this.currentPage)});

				this.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '#', title: 'Loading ...'}
				]);

				// Load it directly from the server.

				application = new ApplicationModel({'id': application_id});
				application.fetch({
					success: function(model, response, options) {
						applicationViewInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			}
		},

		versionView: function(version_id) {
			this.ensureVisible('workspaces');

			var _self = this;
			function versionViewInner(version) {
				// Add to the collection, and refetch, so it's tied
				// to the collection's events.
				_self.context.versions.add(version);
				version = _self.context.versions.get(version.id);

				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{
						href: '/workspace/' + version.attributes.workspace.id + '/applications',
						title: version.attributes.workspace.name
					},
					{
						href: '/application/' + version.attributes.application.id,
						title: version.attributes.application.name
					},
					{
						href: '/version/' + version.attributes.id,
						title: 'Version ' + version.attributes.version
					}
				]);

				_self.currentMainView = new VersionDetailView({
					model: version,
					el: $('.mainarea', this.currentPage)
				});
			}

			// Try to load the version first.
			var version = this.context.versions.get(version_id);
			if (version) {
				versionViewInner(version);

				// Refresh the version.
				version.fetch();
			} else {
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', this.currentPage)});

				this.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '#', title: 'Loading ...'}
				]);

				// Load it directly from the server.

				version = new VersionModel({'id': version_id});
				version.fetch({
					success: function(model, response, options) {
						versionViewInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			}
		},

		nodeList: function() {
			this.ensureVisible('nodes');

			this.currentMainView = new NodeListView({
				collection: this.context.nodes,
				el: $('.mainarea', pages.nodes)
			});

			// Refresh the list of nodes.
			this.context.nodes.fetch();

			// Reset the active flag on all nodes.
			this.context.nodes.invoke('set', {active: false});

			this.breadcrumbs([{href: '/node/list', title: 'Nodes'}]);

			this.currentMainView.render();
			this.currentMainView.startLoadingFull();
		},

		nodeDetail: function(node_id) {
			this.ensureVisible('nodes');

			var _self = this;
			function nodeDetailInner(node) {
				// Add to the collection, and refetch, so it's tied
				// to the collection's events.
				_self.context.nodes.add(node);
				node = _self.context.nodes.get(node.id);
				node.set({active: true});

				_self.breadcrumbs([
					{href: '/node/list', title: 'Nodes'},
					{href: '/node/' + node_id, title: node.attributes.name}
				]);

				_self.currentMainView = new NodeDetailView({
					model: node,
					el: $('.mainarea', pages.nodes)
				});
			}

			// Try to load from the collection first.
			var node = this.context.nodes.get(node_id);
			if (node) {
				nodeDetailInner(node)
			} else {
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', pages.nodes)});

				this.breadcrumbs([
					{href: '/node/list', title: 'Nodes'},
					{href: '#', title: 'Loading node ' + node_id + '...'}
				]);

				// Load it directly from the server.
				node = new NodeModel({'id': node_id});
				node.fetch({
					success: function(model, response, options) {
						nodeDetailInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			}
		},

		administrationList: function() {
			this.ensureVisible('administration');

			this.context.administrations.invoke('set', {active: false});

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'}
			]);

			this.currentMainView = new AdministrationListView({
				collection: this.context.administrations,
				el: $('.mainarea', pages.administration)
			});
		},

		yourProfile: function() {
			this.ensureVisible('administration');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/profile', title: 'Your Profile'}
			]);

			this.adminSetActive();

			this.currentMainView = new ProfileView({
				el: $('.mainarea', pages.administration)
			});

			// Load the data manually.
			// TODO: Error handling.
			var _self = this;
			$.getJSON(
				'/profile?format=json',
				function(data)
				{
					_self.currentMainView.render(data.data.apikey);
				}
			);
		},

		userList: function() {
			this.ensureVisible('administration');

			this.adminSetActive();

			this.currentMainView = new UserListView({
				collection: this.context.users,
				el: $('.mainarea', pages.administration)
			});

			// Refresh the list of nodes.
			this.context.users.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/user/list', title: 'User List'}
			]);

			this.currentMainView.render();
			if (this.context.users.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		userEdit: function(user_id) {
			this.ensureVisible('administration');
			this.adminSetActive('/user/list');

			var _self = this;
			function userEditInner(user) {
				var crumbs = [
					{href: '/administration/list', title: 'Administration'},
					{href: '/user/list', title: 'Users'}
				];
				if (user) {
					crumbs.push({href: '/user/' + user_id, title: 'Edit user ' + user.attributes.name});
				} else {
					crumbs.push({href: '/user/create', title: 'Create user'})
				}
				_self.breadcrumbs(crumbs);

				_self.currentMainView = new UserEditView({
					model: user,
					el: $('.mainarea', pages.administration)
				});
			}

			if (user_id) {
				// Always fetch from the server before editing.
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', pages.administration)});

				this.breadcrumbs([
					{href: '/administration/list', title: 'Administration'},
					{href: '/user/list', title: 'Users'},
					{href: '#', title: 'Loading user ' + user_id + '...'}
				]);

				var user = new UserModel({'id': user_id});
				user.fetch({
					success: function(model, response, options) {
						userEditInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			} else {
				// Load empty user.
				userEditInner();
			}
		},

		roleList: function() {
			this.ensureVisible('administration');

			this.adminSetActive();

			this.currentMainView = new RoleListView({
				collection: this.context.roles,
				el: $('.mainarea', pages.administration)
			});

			// Refresh the list of roles.
			this.context.roles.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/list', title: 'Role List'}
			]);

			this.currentMainView.render();
			if (this.context.roles.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		roleEdit: function(role_id) {
			this.ensureVisible('administration');
			this.adminSetActive('/role/list');

			var _self = this;
			function roleEditInner(role) {
				var crumbs = [
					{href: '/administration/list', title: 'Administration'},
					{href: '/role/list', title: 'Roles'}
				];
				if (role) {
					crumbs.push({href: '/role/' + role_id, title: 'Edit Role ' + role.attributes.name});
				} else {
					crumbs.push({href: '/role/create', title: 'Create role'})
				}
				_self.breadcrumbs(crumbs);

				_self.currentMainView = new RoleEditView({
					model: role,
					el: $('.mainarea', pages.administration)
				});
			}

			if (role_id) {
				// Always fetch from the server before editing.
				this.currentMainView = new GenericLoadingView({el: $('.mainarea', pages.administration)});

				this.breadcrumbs([
					{href: '/administration/list', title: 'Administration'},
					{href: '/role/list', title: 'Roles'},
					{href: '#', title: 'Loading role ' + role_id + '...'}
				]);

				var role = new RoleModel({'id': role_id});
				role.fetch({
					success: function(model, response, options) {
						roleEditInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			} else {
				// Load empty role.
				roleEditInner();
			}
		},

		roleAllocationList: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.currentMainView = new RoleAllocationListView({
				collection: this.context.roleallocations,
				el: $('.mainarea', pages.administration)
			});

			// Refresh the list of role allocations.
			this.context.roleallocations.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/allocation/list', title: 'Role Allocations'}
			]);

			this.currentMainView.render();
			if (this.context.roleallocations.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		roleAllocationAssign: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/role/allocation/list');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/allocation/list', title: 'Role Allocations'},
				{href: '/role/allocation/assign', title: 'Assign Role'}
			]);

			this.currentMainView = new RoleAllocationAssignView({
				el: $('.mainarea', pages.administration)
			});

			this.currentMainView.render();

			// Refresh all data from the server.
			this.context.roles.fetch();
			this.context.users.fetch();
			this.context.workspaces.fetch();
		},

		adminHealthJobs: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/job/list/health');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/job/list/health', title: 'Health Checks'}
			]);

			this.genericJobsListPage('/job/list/health?format=json', 'Health Checks');
		},

		adminPeriodicJobs: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/job/list/periodic');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/job/list/periodic', title: 'Periodic Tasks'}
			]);

			this.genericJobsListPage('/job/list/periodic?format=json', 'Periodic Tasks');
		},

		adminRouterDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/router/dump', title: 'Router Dump'}
			]);

			this.genericDataTemplatePage('/router/dump?format=json', RouterDumpView);
		},

		adminConfigurationDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/configuration/dump', title: 'Configuration Dump'}
			]);

			this.genericDataTemplatePage('/configuration/dump?format=json', ConfigurationDumpView);
		},

		adminPluginsDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/configuration/plugins', title: 'Plugins'}
			]);

			this.genericDataTemplatePage('/configuration/plugins?format=json', PluginsDumpView);
		},

		defaultAction: function(args) {
			this.ensureVisible('404');
			console.log('Default!');
			console.log(args);
		}
	});

	return AppRouter;
});
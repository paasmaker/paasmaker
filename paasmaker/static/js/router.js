define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/breadcrumb.html',
	'models/node',
	'models/user',
	'models/role',
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
	'views/administration/role-edit'
], function($, _, Backbone,
	breadcrumbTemplate,
	NodeModel,
	UserModel,
	RoleModel,
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
	RoleEditView
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
			this.route(/^workspace\/(\d+)\/applications$/, 'applicationList');
			this.route(/^workspace\/(\d+)$/, 'workspaceEdit');
			this.route('workspace/create', 'workspaceEdit');

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

		applicationList: function(workspace_id) {
			this.ensureVisible('workspaces');
			console.log("Application list");
			console.log(workspace_id);
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

		defaultAction: function(args) {
			this.ensureVisible('404');
			console.log('Default!');
			console.log(args);
		}
	});

	return AppRouter;
});
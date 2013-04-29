define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/breadcrumb.html',
	'models/node',
	'views/node/list',
	'views/workspace/sidebar',
	'views/node/sidebar',
	'views/node/detail',
	'views/administration/sidebar',
	'views/administration/profile',
	'views/administration/list'
], function($, _, Backbone,
	breadcrumbTemplate,
	NodeModel,
	NodeListView,
	WorkspaceSidebarList,
	NodeSidebarList,
	NodeDetailView,
	AdministrationSidebarList,
	ProfileView,
	AdministrationListView
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
			this.route('profile', 'userProfile');

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
				if (node) {
					_self.context.nodes.add(node);
					node = _self.context.nodes.get(node.id);
					node.set({active: true});

					_self.breadcrumbs([
						{href: '/node/list', title: 'Nodes'},
						{href: '/node/' + node_id, title: node.attributes.name}
					]);
				} else {
					_self.breadcrumbs([
						{href: '/node/list', title: 'Nodes'},
						{href: '#', title: 'Loading node ' + node_id + '...'}
					]);
				}

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
				// Load it directly from the server.
				node = new NodeModel({'id': node_id});
				node.fetch({
					success: function(model, response, options) {
						nodeDetailInner(model);
					}
				});

				// Render with a blank node, so the user gets feedback.
				nodeDetailInner();
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

		userProfile: function() {
			this.ensureVisible('administration');

			// Mark us as active.
			this.context.administrations.invoke('set', {active: false});
			this.context.administrations.findWhere({path: window.location.pathname}).set({active: true});

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/profile', title: 'Your Profile'}
			]);

			this.currentMainView = new ProfileView({
				el: $('.mainarea', pages.administration)
			});

			// Load the data manually.
			// TODO: Error handling.
			$.getJSON(
				'/profile?format=json',
				function(data)
				{
					pv.render(data.data.apikey);
				}
			);
		},

		defaultAction: function(args) {
			this.ensureVisible('404');
			console.log('Default!');
			console.log(args);
		}
	});

	return AppRouter;
});
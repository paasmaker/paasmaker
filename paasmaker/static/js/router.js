define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/breadcrumb.html',
	'views/node/list',
	'views/workspace/sidebar',
	'views/node/sidebar'
], function($, _, Backbone,
	breadcrumbTemplate,
	NodeListView,
	WorkspaceSidebarList,
	NodeSidebarList
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

			// TODO: Catch the default.
			//this.route('*path', 'defaultAction');
		},

		ensureVisible: function(section) {
			var _self = this;
			_.each(pages, function(value, key, list) {
				if(section != key) {
					value.hide();
				}
			});
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
				}
				if(section == 'workspaces') {
					sidebars[section] = new WorkspaceSidebarList({
						collection: this.context.workspaces,
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

			var nlv = new NodeListView({
				collection: this.context.nodes,
				el: $('.mainarea', pages.nodes)
			});

			this.context.nodes.fetch();

			this.breadcrumbs([{href: '/node/list', title: 'Node List'}])
		},

		nodeDetail: function(node_id) {
			this.ensureVisible('nodes');

			this.breadcrumbs([
				{href: '/node/list', title: 'Node List'},
				{href: '/node/' + node_id, title: 'Node ' + node_id}
			]);
		},

		defaultAction: function(args) {
			this.ensureVisible('404');
			console.log('Default!');
			console.log(args);
		}
	});

	return AppRouter;
});
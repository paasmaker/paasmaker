define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/node/sidebar.html',
	'views/node/sidebar-entry'
], function($, _, Backbone, context, Bases, nodeSidebarTemplate, SidebarEntryView){
	var NodeSidebarListView = Bases.BaseView.extend({
		initialize: function() {
			// Render a blank template to start off with.
			this.$el.html(Bases.errorLoadingHtml + nodeSidebarTemplate({nodes: [], context: context}));

			// Add our refresh button.
			this.$('.controls').append($('<a href="#" class="refresh"><i class="icon-refresh"></i></a>'));

			// And when the data comes in, update the whole list.
			this.collection.on('request', this.startLoadingInline, this);
			this.collection.on('sync', this.render, this);
			this.collection.on('add', this.addNode, this);
			this.collection.on('error', this.loadingError, this);
			this.startLoadingInline();
		},
		addNode: function(node) {
			// Add a container for this node, and a view.
			var nodeContainer = $('<li class="node node-' + node.attributes.id + '"></li>');
			this.$('.nav-list').append(nodeContainer);

			var sev = new SidebarEntryView({
				el: nodeContainer,
				model: node
			});
		},
		render: function() {
			this.doneLoading();
		},
		events: {
			"click a.refresh": "refreshList"
		},
		refreshList: function(e) {
			this.collection.fetch();
			e.preventDefault();
		}
	});

	return NodeSidebarListView;
});
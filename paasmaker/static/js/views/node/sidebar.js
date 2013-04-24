define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'tpl!templates/node/sidebar.html',
	'views/node/sidebar-entry'
], function($, _, Backbone, context, nodeSidebarTemplate, SidebarEntryView){
	var NodeSidebarListView = Backbone.View.extend({
		initialize: function() {
			// Render a blank template to start off with.
			this.$el.html(nodeSidebarTemplate({nodes: [], context: context}));

			// And when the data comes in, update the whole list.
			this.collection.on('request', this.loading, this);
			this.collection.on('sync', this.render, this);
			this.collection.on('add', this.addNode, this);
			//this.collection.on('all', this.allEv, this);
			this.loading();
		},
		allEv: function(ev, arg) {
			console.log("All ev");
			console.log(ev);
			console.log(arg);
		},
		addNode: function(node) {
			// Add a container for this node, and a view.
			var nodeContainer = $('<div class="node node-' + node.attributes.id + '"></div>');
			this.$('.node-list').append(nodeContainer);

			var sev = new SidebarEntryView({
				el: nodeContainer,
				model: node
			});
		},
		loading: function() {
			this.$('.loading').show();
		},
		render: function() {
			this.$('.loading').hide();
		},
		events: {
			"click a": "navigateAway",
		},
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));
			return false;
		}
	});

	return NodeSidebarListView;
});
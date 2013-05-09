define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/node/sidebar-entry.html'
], function($, _, Backbone, context, Bases, NodeSidebarEntryTemplate){
	var NodeSidebarEntryView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('change', this.render, this);
			this.render();
		},
		render: function() {
			this.$el.html(NodeSidebarEntryTemplate({
				context: context,
				node: this.model,
				stateClasses: context.nodes.stateClasses
			}));

			if (this.model.attributes.active) {
				this.$el.addClass("active");
			} else {
				this.$el.removeClass("active");
			}
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return NodeSidebarEntryView;
});
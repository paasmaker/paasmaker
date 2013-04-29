define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'tpl!templates/node/sidebar-entry.html'
], function($, _, Backbone, context, nodeSidebarEntryTemplate){
	var NodeSidebarEntryView = Backbone.View.extend({
		initialize: function() {
			this.model.on('change', this.render, this);
			this.render();
		},
		render: function() {
			this.$el.html(nodeSidebarEntryTemplate({
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
		},
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));
			e.preventDefault();
		}
	});

	return NodeSidebarEntryView;
});
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
				stateClasses: this.stateClasses
			}));
		},
		events: {
			"click a": "navigateAway",
		},
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));
			return false;
		},

		stateClasses: {
			'ACTIVE': { badge: 'badge-success', icon: 'icon-ok' },
			'STOPPED': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'INACTIVE': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'DOWN': { badge: 'badge-important', icon: 'icon-ban-circle' }
		}
	});

	return NodeSidebarEntryView;
});
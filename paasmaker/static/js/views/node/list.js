define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'tpl!templates/node/list.html'
], function($, _, Backbone, context, nodeListTemplate){
	var NodeListView = Backbone.View.extend({
		initialize: function() {
			this.collection.on('request', this.loading, this);
			this.collection.on('sync', this.render, this);
			this.loading();
		},
		loading: function() {
			this.$('.loading').show();
		},
		render: function() {
			this.$el.html(nodeListTemplate({
				nodes: this.collection.models,
				context: context
			}));
		},
		events: {
			"click a": "navigateAway",
		},
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));
			return false;
		}
	});

	return NodeListView;
});
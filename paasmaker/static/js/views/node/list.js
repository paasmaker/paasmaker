define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/node/list.html'
], function($, _, Backbone, context, Bases, nodeListTemplate){
	var NodeListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(nodeListTemplate({
				nodes: [],
				context: context
			}));
		},
		destroy: function() {
			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(nodeListTemplate({
				nodes: this.collection.models,
				context: context,
				stateClasses: this.collection.stateClasses
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return NodeListView;
});
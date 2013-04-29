define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/node/instances.html'
], function($, _, Backbone, context, Bases, util, nodeInstancesListTemplate){
	var NodeInstancesListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(nodeInstancesListTemplate({
				instances: this.collection.models,
				context: context
			}));

			this.startLoadingFull();
		},
		destroy: function() {
			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
		},
		render: function() {
			this.doneLoading();

			this.$el.html(nodeInstancesListTemplate({
				instances: this.collection.models,
				context: context
			}));

			util.shrinkUuids(this.$el);

			return this;
		}
	});

	return NodeInstancesListView;
});
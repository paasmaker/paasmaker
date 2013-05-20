define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/workspace/list.html'
], function($, _, Backbone, context, Bases, WorkspaceListTemplate){
	var WorkspaceListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(WorkspaceListTemplate({
				workspaces: [],
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

			this.$el.html(WorkspaceListTemplate({
				workspaces: this.collection.models,
				context: context
			}));

			return this;
		},
		events: {
			"click a.virtual": "navigateAway",
		}
	});

	return WorkspaceListView;
});
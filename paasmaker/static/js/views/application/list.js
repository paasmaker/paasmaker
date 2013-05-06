define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/application/list.html'
], function($, _, Backbone, context, Bases, ApplicationListTemplate){
	var ApplicationListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(ApplicationListTemplate({
				workspace: this.options.workspace,
				applications: [],
				context: context,
				healthClasses: this.collection.healthClasses
			}));
		},
		destroy: function() {
			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationListTemplate({
				workspace: this.options.workspace,
				applications: this.collection.models,
				context: context,
				healthClasses: this.collection.healthClasses
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return ApplicationListView;
});
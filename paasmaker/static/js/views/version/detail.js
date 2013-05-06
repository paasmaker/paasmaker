define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/version/detail.html'
], function($, _, Backbone, context, Bases, VersionDetailTemplate){
	var VersionDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);

			this.$el.html(VersionDetailTemplate({
				version: this.model,
				context: context
			}));
		},
		destroy: function() {
			this.model.off('request', this.startLoadingFull, this);
			this.model.off('change', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(VersionDetailTemplate({
				version: this.model,
				context: context
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return VersionDetailView;
});
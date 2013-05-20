define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/role-list.html'
], function($, _, Backbone, context, Bases, RoleListTemplate){
	var RoleListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(RoleListTemplate({
				roles: [],
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

			this.$el.html(Bases.errorLoadingHtml + RoleListTemplate({
				roles: this.collection.models,
				context: context
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return RoleListView;
});
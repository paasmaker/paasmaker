define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/user-list.html'
], function($, _, Backbone, context, Bases, UserListTemplate){
	var UserListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(UserListTemplate({
				users: [],
				context: context
			}));
		},
		destroy: function() {
			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
		},
		render: function() {
			this.doneLoading();

			this.$el.html(Bases.errorLoadingHtml + UserListTemplate({
				users: this.collection.models,
				context: context
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return UserListView;
});
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/administration/profile.html'
], function($, _, Backbone, context, Bases, util, ProfileTemplate){
	var ProfileView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(ProfileTemplate({
				context: context,
				apikey: 'loading'
			}));

			this.startLoadingFull();
		},
		render: function(apikey) {
			this.$el.html(ProfileTemplate({
				context: context,
				apikey: apikey
			}));

			return this;
		}
	});

	return ProfileView;
});
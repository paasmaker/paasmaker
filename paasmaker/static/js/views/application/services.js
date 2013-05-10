define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/application/services.html'
], function($, _, Backbone, context, Bases, ApplicationServicesTemplate){
	var ApplicationServicesView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html('<h1>Services</h1>');
			this.startLoadingFull();
		},
		destroy: function() {
		},
		dataReady: function(data) {
			this.services = data.data;
			this.render();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationServicesTemplate({
				services: this.services,
				context: context
			}));

			return this;
		},
		events: {
			"click a.virtual": "navigateAway",
			"click a.showCredentials": "showCredentials"
		},
		showCredentials: function(e) {
			e.preventDefault();

			var el = $(e.currentTarget);
			var credentials = $('pre', el.parent());
			credentials.slideToggle();
		}
	});

	return ApplicationServicesView;
});
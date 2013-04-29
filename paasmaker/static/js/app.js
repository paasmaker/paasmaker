define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'router'
], function($, _, Backbone, Context, Router) {
	var module = {};

	module.initialize = function() {
		// Manually set up the router. This stops loops between the
		// context and the router.
		Context.initialize();
		Context.router = new Router();
		Context.router.context = Context;
		Context.router.initialize();

		// Make the links in the header navigate using the router.
		$('.navbar .brand, .navbar .nav-collapse a.virtual').click(function(e) {
			var el = $(this);
			Context.navigate(el.attr('href'));
			return false;
		});

		// Hide the page loading div.
		$('.page-loading').fadeOut();
		$('#page-container').fadeIn();

		// Kick off the controllers.
		// CAUTION: This ends control of this function.
		Backbone.history.start({pushState: true});
	};

	return module;
});
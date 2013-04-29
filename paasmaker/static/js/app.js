define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'router',
	'collections/administrations'
], function($, _, Backbone, context, Router, AdministrationCollection) {
	var module = {};

	module.initialize = function() {
		// Manually set up the router. This stops loops between the
		// context and the router.
		context.initialize();
		context.router = new Router();
		context.router.context = context;
		context.router.initialize();

		// Make the links in the header navigate using the router.
		$('.navbar .brand, .navbar .nav-collapse a.virtual').click(function(e) {
			var el = $(this);
			context.navigate(el.attr('href'));
			return false;
		});

		// Create the administration collection.
		context.administrations = new AdministrationCollection();
		context.administrations.add([
			{name: 'Your Profile', path: '/profile'}
		]);

		// Hide the page loading div.
		$('.page-loading').fadeOut();
		$('#page-container').fadeIn();

		// Kick off the controllers.
		// CAUTION: This ends control of this function.
		Backbone.history.start({pushState: true});
	};

	return module;
});
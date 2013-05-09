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

		// Set up the web socket for getting stats, job, and other data
		// from the pacemaker (or long poll -- handled by socket.io)
		// CAUTION: This version of socket.io has been modified
		// so it falls back to XHR when the websocket connection fails.

		// When not connected, we use a "flatline" image for the logo.
		var logo = $('.brand .connected');
		var connectedLogoSrc = logo.attr('src');
		var disconnectedLogoSrc = $('.brand .disconnected').attr('src');
		logo.attr('src', disconnectedLogoSrc);

		context.streamSocket = new io.connect(window.location.protocol + '//' + window.location.host, {'connect timeout': 10000});
		context.streamSocket.on('connect', function() {
			logo.attr('src', connectedLogoSrc);
		});
		context.streamSocket.on('disconnect', function() {
			logo.attr('src', disconnectedLogoSrc);
			context.streamSocket.socket.reconnect();
		});

		// Disable PUT requests.
		Backbone.emulateHTTP = true;

		// Replace the backbone default sync with one that handles
		// the errors slightly differently, and also puts any outgoing
		// data into a "data" section.
		var oldBackboneSync = Backbone.sync;
		Backbone.sync = function(method, model, options) {
			if(method === 'create' || method === 'update') {
				// Wrap the values into the "data" section of the request.
				options.attrs = {data: model.toJSON(options)};

				// Also, catch the case where the server returns
				// a 200 code, but there are actually errors.
				var oldSuccessHandler = options.success;
				options.success = function(data, xhr, resultoptions) {
					if (data.errors && data.errors.length > 0) {
						// Call the error handler instead.
						if (options.error) {
							options.error(data, xhr, options);
						}
					} else {
						if (oldSuccessHandler) {
							oldSuccessHandler(data, xhr, options);
						}
					}
				}
			}
			oldBackboneSync(method, model, options);
		};

		// Make the links in the header navigate using the router.
		$('.navbar .brand, .navbar .nav-collapse a.virtual').click(function(e) {
			// This if wrapper allows middle clicks to open new tabs
			// with the target URL.
			// Based on http://stackoverflow.com/questions/1795734/triggering-onclick-event-using-middle-click
			if (e.which != 2) {
				var el = $(this);
				context.navigate(el.attr('href'));
				e.preventDefault();
			} else {
				e.stopPropagation();
			}
		});

		// Create the administration collection.
		context.administrations = new AdministrationCollection();
		context.administrations.add([
			{name: 'Your Profile', path: '/profile'}
		]);

		if (context.hasPermission('USER_LIST')) {
			context.administrations.add([
				{name: 'Users', path: '/user/list'}
			]);
		}
		if (context.hasPermission('ROLE_LIST')) {
			context.administrations.add([
				{name: 'Roles', path: '/role/list'}
			]);
		}
		if (context.hasPermission('ROLE_ASSIGN')) {
			context.administrations.add([
				{name: 'Role Allocations', path: '/role/allocation/list'}
			]);
		}
		if (context.hasPermission('HEALTH_CHECK')) {
			context.administrations.add([
				{name: 'Health Checks', path: '/job/list/health'}
			]);
		}
		if (context.hasPermission('SYSTEM_ADMINISTRATION')) {
			context.administrations.add([
				{name: 'Periodic Tasks', path: '/job/list/periodic'},
				{name: 'Router Table Dump', path: '/router/dump'},
				{name: 'System Configuration', path: '/configuration/dump'},
				{name: 'Plugins', path: '/configuration/plugins'}
			]);
		}

		// Hide the page loading div.
		$('.page-loading').fadeOut();
		$('#page-container').fadeIn();

		// Kick off the controllers.
		// CAUTION: This ends control of this function.
		Backbone.history.start({pushState: true});
	};

	return module;
});
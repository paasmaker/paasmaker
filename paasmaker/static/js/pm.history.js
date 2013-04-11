/* Paasmaker - Platform as a Service
 *
 * pm.history.js - manage browser history and ajax versus page reload links
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

// Mapping of URLs that can be handled by the JavaScript code (i.e. without a page refresh)
// Note: additions here should always be reflected in the relevant controller class, with client_side_render()
pm.routingTable = [
	[ /^\/profile/, pm.admin.profile ],
	[ /^\/configuration\/plugins/, pm.admin.plugins ],
	[ /^\/configuration\/dump/, pm.admin.config_dump ],
	[ /^\/user\/list/, pm.admin.user_list ],
	[ /^\/role\/list/, pm.admin.role_list ],
	[ /^\/role\/allocation\/list/, pm.admin.allocation_list ],
	[ /^\/node\/list/, pm.node.list ],
	[ /^\/node\/\d+\/?$/, pm.node.detail ],
	[ /^\/job\/list\//, pm.jobs.list ],
	[ /^\/job\/detail\//, pm.jobs.single ],
	[ /^\/workspace\/\d+\/applications\/new\/?$/, pm.upload ],
	[ /^\/application\/\d+\/newversion\/?$/, pm.upload ],
	[ /^\/workspace\/create\/?$/, pm.workspace.edit ],
	[ /^\/workspace\/\d+\/?$/, pm.workspace.edit ],
	[ /^\/workspace\/\d+\/applications\/?$/, pm.workspace.view ],
	[ /^\/application\/\d+\/services\/?$/, pm.application.services ],
	[ /^\/application\/\d+\/?$/, pm.application.view ],
	[ /^\/version\/\d+\/?$/, pm.version ],
	[ /^\/service\/import\/\d+\/?$/, pm.service.import_service ],
	[ /^\/service\/export\/\d+\/?$/, pm.service.export_service ]
];

pm.history = (function() {
	var current_address;
	var exit_handlers = [];

	return {
		/**
		 * Tests pathname against the regexps in pm.routingTable,
		 * and returns the controller object of the first match
		 */
		getRoute: function(pathname) {
			for (var i=0, compare; compare = pm.routingTable[i]; i++) {
				if (compare[0].test(pathname)) {
					return compare[1];
				}
			}
			return false;
		},

		/**
		 * Draw a loading spinner and translucent overlay on top of the
		 * element el, or over the whole view if el isn't specified.
		 */
		showLoadingOverlay: function(el) {
			if (el) {
				el = $(el);
			} else {
				el = $('#main');
			}
			var overlay = $("<div class=\"loading-overlay\"><img src=\"/static/img/spinner32.gif\" alt=\"\"></div>");
			el.append(overlay);
			overlay.animate({ opacity: 0.8 });
		},

		/**
		 * Remove the loading spinner on the element el, or
		 * remove all spinners if el isn't specified.
		 */
		hideLoadingOverlay: function(el) {
			if (el) {
				el = $(el);
			} else {
				el = $(document);
			}
			$('.loading-overlay', el).remove();
		},

		/**
		 * Register the object in function_object as something to run when the user
		 * navigates away from the current view. Use for clearing timeouts,
		 * stopping auto-refresh widgets, cancelling uploads, etc.
		 *
		 * @param function_object object with properties:
		 *  - fn: the function itself to run
		 *  - scope: value of "this" when fn is called
		 *  - arguments: array of arguments to pass
		 *
		 * (The argument can also just be the function if it
		 *  takes no arguments and its scope is irrelevant.)
		 */
		registerExitHandler: function(function_object) {
			var object_to_store = {};

			if (typeof function_object == 'function') {
				object_to_store.fn = function_object;
			} else {
				object_to_store = function_object;
			}
			if (!object_to_store.scope) {
				object_to_store.scope = pm.history;
			}
			if (!object_to_store.arguments) {
				object_to_store.arguments = [];
			}

			exit_handlers.push(object_to_store);
		},

		/**
		 * Run any handlers registered with registerExitHandler
		 * (i.e. the user is navigating away from the current view.)
		 */
		runExitHandlers: function() {
			while (exit_handlers.length) {
				var function_object = exit_handlers.pop();
				function_object.fn.apply(function_object.scope, function_object.arguments);
			}
		},

		/**
		 * event handler for changes to page history; also runs at page load when the
		 * server-side controller directs us to an empty main.html (i.e. for pages
		 * that are served by handlebars templates instead of tornado templates)
		 *
		 * when switching to a new view, show a loading spinner and make sure to
		 * close all WebSocket listeners; the new view will start its own if needed
		 */
		onpopstate: function(e) {
			if (e.state && e.state.handle_in_js) {
				var address = document.location.pathname;
				// if (address == current_address) { return false; }
				current_address = address;

				// TODO: update pages that need this with registerExitHandler
				pm.data.removeListeners();

				pm.history.showLoadingOverlay();
				pm.history.runExitHandlers();

				var module = pm.history.getRoute(address);
				module.switchTo.apply(module, [e.state]);
			}
		},

		init: function() {
			// At page load, add an event handler for all clicks. If the click was on a link,
			// check to see if it's pointing to a page that we can serve up without a page
			// reload. If so, do a pushState so the history event handler will respond.
			$(document).on('click', function(e) {
				if (e.target.tagName == 'A') {
					if (e.target.className.indexOf('job-action-button') !== -1) {
						// action button: these only occur on ajax-generated pages, so find
						// the controller for the current page and run its actionButton method
						e.preventDefault();
						var module = pm.history.getRoute(current_address);
						module.actionButton.apply(module, arguments);

					} else {
						// regular link: check if we should intercept it
						var parsed_url = e.target.href.match(/^https?\:\/\/[^\/]+(\/.*)$/);
						if (parsed_url && pm.history.getRoute(parsed_url[1])) {
							e.preventDefault();
							window.history.pushState({ handle_in_js: true }, '', parsed_url[1]);
							pm.history.onpopstate({ state: { handle_in_js: true } });
						}
					}
				}
			});

			window.addEventListener('popstate', pm.history.onpopstate);
			// if (foo) {
			// 	pm.history.onpopstate({ state: { handle_in_js: true } });
			// }
		}
	};
}());

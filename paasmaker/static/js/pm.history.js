/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.history.js - manage browser history and ajax versus page reload links
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
	[ /^\/workspace\/\d+\/applications\/?$/, pm.workspace ],
	[ /^\/application\/\d+\/?$/, pm.application ],
	[ /^\/version\/\d+\/?$/, pm.version ]
];

pm.history = (function() {
	var current_address;

	return {
		getRoute: function(pathname) {
			for (var i=0, compare; compare = pm.routingTable[i]; i++) {
				if (compare[0].test(pathname)) {
					return compare[1];
				}
			}
			return false;
		},

		loadingOverlay: function(el) {
			if (el) {
				el = $(el);
			} else {
				// cover the whole view with a loading spinner
				el = $('#main');
			}
			var overlay = $("<div class=\"loading-overlay\"><img src=\"/static/img/spinner32.gif\" alt=\"\"></div>");
			el.append(overlay);
			overlay.animate({ opacity: 0.8 });
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
				if (address == current_address) { return false; }
				current_address = address;

				pm.data.removeListeners();
				pm.history.loadingOverlay();
				var module = pm.history.getRoute(address);
				module.switchTo.apply(module);
			}
		},

		init: function() {
			// At page load, add an event handler for all clicks. If the click was on a link,
			// check to see if it's pointing to a page that we can serve up without a page
			// reload. If so, do a pushState so the history event handler will respond.
			$(document).on('click', function(e) {
				if (e.target.tagName == 'A') {
					var parsed_url = e.target.href.match(/^https?\:\/\/[^\/]+(\/.*)$/);
					if (parsed_url && pm.history.getRoute(parsed_url[1])) {
						e.preventDefault();
						window.history.pushState({ handle_in_js: true }, '', parsed_url[1]);
						pm.history.onpopstate({ state: { handle_in_js: true } });
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

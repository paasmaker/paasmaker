/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.admin.js - interface for administration pages
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.admin = {};

pm.admin.profile = (function() {

	return {

		switchTo: function() {
			pm.data.api({
				endpoint: 'profile',
				callback: function(data) {
					$('#main').html(pm.handlebars.user_profile({ current_user: data }));
				}
			});
		}

	};
}());

/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.overview.js - overview dashboard interface
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.overview = (function() {


	return {

		init: function() {
			// TODO: showLoadingSpinner or similar
			$('#main').empty();

			$('#main').html("<p style=\"text-align:center;padding:50px\">Overview goes here!</p>");
		}

	};
}());

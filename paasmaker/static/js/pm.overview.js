/* Paasmaker - Platform as a Service
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
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

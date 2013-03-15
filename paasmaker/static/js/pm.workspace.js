/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.workspace = (function() {


	return {

		// event handler for changes in the workspace switcher
		switchTo: function(e) {
			var workspace_id = $(e.target).val();

			console.log("Switching to " + workspace_id);

			if (workspace_id == "overview") {
				pm.overview.init();
			} else {
				// do stuff
			}
		}

	};
}());

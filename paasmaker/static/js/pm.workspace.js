/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.workspace = (function() {
	var app_menu = {};

	return {

		updateAppMenu: function(new_workspace_id) {
			if (new_workspace_id == app_menu.current_workspace_id) {
				return false;	// don't redraw if unnecessary, but TODO: handle edits, etc.
			}
			app_menu.current_workspace_id = new_workspace_id
		
			pm.data.api({
			  endpoint: "workspace/" + new_workspace_id + "/applications",
				callback: function(data) {
					$('#app_menu_wrapper').html(pm.handlebars.app_menu(data))
				}
			});

		},

		switchTo: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\//);
		
			if ($('#app_menu_wrapper').length && $('#app_view_main').length) {
				$('#app_view_main').empty();
			} else {
				$('#main').empty();
				$('#main').append(
					$("<div id=\"app_menu_wrapper\">"),
					$("<div id=\"app_view_main\" class=\"with-application-list\">")
				);
				pm.history.loadingOverlay();
			}
			
			pm.workspace.updateAppMenu(url_match[1]);
		
			pm.data.api({
				endpoint: 'workspace/' + url_match[1],	// or just document.location?
				callback: function(data) {
					$('#app_view_main').html(pm.handlebars.workspace_main(data));
					$('.loading-overlay').remove();
					pm.stats.routerstats.redraw();
				}
			});
		}

	};
}());

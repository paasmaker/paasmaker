/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.workspace = (function() {

	return {

		updateAppMenu: function(new_workspace_id, highlight_key) {
			// if (new_workspace_id == app_menu.current_workspace_id) {
			// 	if ($('#app_menu_wrapper a').length) {
			// 		// don't redraw if unnecessary, but TODO: handle edits, etc.
			// 		// TODO: find a better detection method?
			// 		return false;
			// 	} else {
			// 		// redraw, but a new ajax roundtrip shouldn't be needed
			// 		pm.workspace.redrawAppMenu();
			// 	}
			// }
			// app_menu.current_workspace_id = new_workspace_id

			var bootstrap_health_classes = {
				'OK': { badge: 'badge-success', icon: 'icon-ok' },
				'WARNING': { badge: 'badge-warning', icon: 'icon-warning-sign' },
				'ERROR': { badge: 'badge-important', icon: 'icon-ban-circle' }
			};

			pm.data.api({
				endpoint: "workspace/" + new_workspace_id + "/applications",
				callback: function(data) {
					processed_app_list = [];
					data.applications.forEach(function(app) {
						if (highlight_key && highlight_key.application && highlight_key.application == app.id) {
							app.is_active = true;
						}
						app.health_class = bootstrap_health_classes[app.health];
						processed_app_list.push(app);
					});
					data.applications = processed_app_list;

					pm.workspace.redrawAppMenu(data, highlight_key);
				}
			});
		},

		redrawAppMenu: function(app_data, highlight_key) {
			$('#app_menu_wrapper').html(pm.handlebars.app_menu(app_data));
			$('#app_menu_wrapper li.application').each(function(i, el) {
				var app_id = $(el).data('application-id');
				pm.data.api({
					endpoint: "application/" + app_id,
					callback: function(data) {
						if (data.current_version) {
							processed_version_list = [];
							data.versions.forEach(function(version) {
								if (version.id == data.current_version.id) {
									version.is_current = true;
								}
								if (highlight_key && highlight_key.version && highlight_key.version == version.id) {
									version.is_active = true;
								}
								processed_version_list.push(version);
							});
							data.versions = processed_version_list;
						}
						$(el).after(pm.handlebars.app_menu_versions(data));
					}
				});
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
				pm.history.loadingOverlay("#app_view_main");
			}

			pm.workspace.updateAppMenu(url_match[1]);

			pm.data.api({
				endpoint: 'workspace/' + url_match[1],	// or just document.location?
				callback: function(data) {
					$('#app_view_main').html(pm.handlebars.workspace_main(data));
					$('.loading-overlay').remove();
					pm.stats.workspace.redraw();
				}
			});
		}

	};
}());

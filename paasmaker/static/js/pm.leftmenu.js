/* Paasmaker - Platform as a Service
 *
 * pm.leftmenu.js - management code for the left-side navigation (list of apps/versions, or list of nodes)
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.leftmenu = (function() {
	var bootstrap_health_classes = {
		'OK': { badge: 'badge-success', icon: 'icon-ok' },
		'WARNING': { badge: 'badge-warning', icon: 'icon-warning-sign' },
		'ERROR': { badge: 'badge-important', icon: 'icon-ban-circle' }
	};

	return {

		updateBreadcrumbs: function(data) {
			$('ul.breadcrumb').empty();

			if (data.workspace) {
				var ws_li = $("<li>");
				$('ul.breadcrumb').append(ws_li);
				if (data.application || data.version || data.suffix) {
					var ws_link = $("<a>", { "href": "/workspace/" + data.workspace.id + "/applications" });
					ws_li.append(ws_link);
					ws_link.text(data.workspace.name);
					ws_li.append("<span class=\"divider\">&middot;</span>");
				} else {
					ws_li.text(data.workspace.name);
				}
			}
			if (data.application) {
				var app_li = $("<li>");
				$('ul.breadcrumb').append(app_li);
				if (data.version || data.suffix) {
					var app_link = $("<a>", { "href": "/application/" + data.application.id });
					app_li.append(app_link);
					app_link.text(data.application.name);
					app_li.append("<span class=\"divider\">&middot;</span>");
				} else {
					app_li.text(data.application.name);
				}
			}
			if (data.version) {
				var ver_li = $("<li>");
				$('ul.breadcrumb').append(ver_li);
				if (data.suffix) {
					var ver_link = $("<a>", { "href": "/version/" + data.version.id });
					ver_li.append(ver_link);
					ver_link.text("Version " + data.version.version);
					ver_li.append("<span class=\"divider\">&middot;</span>");
				} else {
					ver_li.text("Version " + data.version.version);
				}
			}
			if (data.suffix) {
				$('ul.breadcrumb').append(
					$("<li>").text(data.suffix)
				);
			}
		},

		/**
		 * Redraw container elements for the two-column view, if not present, or just clear
		 * them (ready for new content) if they are. Called during the init phase of all two
		 * column views. Also resets all loading spinners to just one for the right column.
		 */
		redrawContainers: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			if ($('#left_menu_wrapper a').length && $('#main_right_view').length) {
				$('#main_right_view').empty();
			} else {
				$('#main').empty();
				$('#main').append(
					$("<div id=\"left_menu_wrapper\">"),
					$("<div id=\"main_right_view\" class=\"with-application-list\">")
				);
			}

			pm.history.hideLoadingOverlay();
			pm.history.showLoadingOverlay("#main_right_view");
		},

		updateAppMenu: function(new_workspace_id, highlight_key) {
			if ($('#left_menu_wrapper').children().length < 1) {
				// if no left menu has already been drawn (by another view),
				// show a spinner in the blank space
				// TODO: something other than .children() may be faster
				pm.history.showLoadingOverlay('#left_menu_wrapper');
			}

			pm.data.api({
				endpoint: "workspace/" + new_workspace_id + "/applications",
				callback: function(data) {
					if (highlight_key && highlight_key.newApplication) { data.new_application_active = true; }

					processed_app_list = [];
					data.applications.forEach(function(app) {
						if (highlight_key && highlight_key.application_id && highlight_key.application_id == app.id) {
							app.is_active = true;
						}
						app.health_class = bootstrap_health_classes[app.health];
						processed_app_list.push(app);
					});
					data.applications = processed_app_list;

					pm.leftmenu.redrawAppMenu(data, highlight_key);
				}
			});
		},

		redrawAppMenu: function(app_data, highlight_key) {
			var new_menu = $(Handlebars.templates.app_menu(app_data));
			var version_requests = [];

			$('li.application', new_menu).each(function(i, el) {
				var app_id = $(el).data('application-id');
				version_requests.push({
					endpoint: "application/" + app_id,
					callback: function(data) {
						processed_version_list = [];
						data.versions.forEach(function(version) {
							if (data.current_version && version.id == data.current_version.id) {
								version.is_current = true;
							}
							if (highlight_key && highlight_key.version_id && highlight_key.version_id == version.id) {
								version.is_active = true;
							}
							if (version.state == 'RUNNING') {
								version.is_running = true;
							}
							processed_version_list.push(version);
						});
						data.versions = processed_version_list;
						$(el).after(Handlebars.templates.app_menu_versions(data));
					}
				});
			});

			pm.data.sequential_get({
				requests: version_requests,
				final_callback: function() {
					$('#left_menu_wrapper').empty().append(new_menu);
				}
			});
		}

	};
}());

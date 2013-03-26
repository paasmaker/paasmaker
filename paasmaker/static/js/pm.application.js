/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.application.js - interface for viewing an application and its versions
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.application = (function() {

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

		getButtonMap: function(version) {
			return {
				register: (version.state == 'PREPARED'),
				start: (version.state == 'READY' || version.state == 'PREPARED'),
				stop: (version.state == 'RUNNING'),
				deregister: (version.state == 'READY'),
				makecurrent: (version.state == 'RUNNING' && !version.is_current),
				delete: (version.state == 'PREPARED' && !version.is_current)
			};
		},

		getHealthString: function(version) {
			var health_string = '';

			if (version.health.overall && version.health.overall == 'OK') {
				health_string += version.health.overall;
			} else {
				for (var instance_type in version.health.types) {
					var h = version.health.types[instance_type];
					if (h.state != 'OK') {
						health_string += instance_type + ': ' + h.state;
						if (h.message) {
							health_string += ' - ' + h.message;
						}
						health_string += '<br>';
					}
				}
			}

			return health_string;
		},

		processVersionData: function(versions, data) {
			var processed_versions = [];

			var modifier = function(version) {
				version.health_string = pm.application.getHealthString(version);
				version.buttons_to_show = pm.application.getButtonMap(version);

				// replicate the behaviour of nice_state(); TODO: icons etc?
				version.display_state = version.state[0] + version.state.substr(1).toLowerCase();

				processed_versions.push(version);
			};

			if (versions.length) {
				versions.forEach(modifier);
				return processed_versions;
			} else {
				modifier(versions);
				return processed_versions[0];
			}
		},

		actionButton: function(e) {
			pm.history.loadingOverlay("#main_right_view");
			pm.data.post({
				endpoint: $(e.target).attr('href'),
				callback: function(data) {
					$('.loading-overlay').remove();
					// pushState so the Back button works, but TODO: this should be in pm.history?
					window.history.pushState({ handle_in_js: true }, '', "/job/detail/" + data.job_id);
					pm.jobs.version_action.switchTo({ job_id: data.job_id, version_id: $(e.target).data('version-id') });
				}
			});
		},

		switchTo: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			if ($('#left_menu_wrapper a').length && $('#main_right_view').length) {
				$('#main_right_view').empty();
			} else {
				$('#main').empty();
				$('#main').append(
					$("<div id=\"left_menu_wrapper\">"),
					$("<div id=\"main_right_view\" class=\"with-application-list\">")
				);
				pm.history.loadingOverlay("#main_right_view");
			}

			pm.data.get_app_parents({
				application_id: url_match[1],
				callback: function(parents) {
					pm.workspace.updateAppMenu(parents.workspace.id, { application: url_match[1] });
					pm.application.updateBreadcrumbs({
						workspace: parents.workspace,
						application: parents.application,
						version: parents.version
					});
				}
			});

			pm.data.api({
				endpoint: 'application/' + url_match[1],	// or just document.location?
				callback: function(data) {
					if (pm.util.hasPermission('APPLICATION_DELETE', data.application.workspace_id)) {
						// check if this app can be deleted, i.e. no versions in READY or RUNNING states
						data.application.can_delete = true;
						for (var i=0, version; version = data.versions[i]; i++) {
							if (version.state == 'READY' || version.state == 'RUNNING') {
								data.application.can_delete = false;
								break;
							}
						}
					}

					data.versions = pm.application.processVersionData(data.versions, data);
					if (data.current_version) {
						data.current_version = pm.application.processVersionData(data.current_version, data);
					}

					// render main template body (but with empty tables)
					$('#main_right_view').html(pm.handlebars.application_versions(data));

					// add rows for each version from separate template file;
					// then fire off a separate API request to get instance counts
					if (data.current_version) {
						$('table.current_version').append(pm.handlebars.application_version_row(data.current_version));
					}
					data.versions.forEach(function(version) {
						$('table.all_versions').append(pm.handlebars.application_version_row(version));

						pm.data.api({
							endpoint: 'version/' + version.id + '/instances',
							callback: function(instance_data) {
								var instance_total = 0;
								for (var type in instance_data.instances) {
									instance_total += instance_data.instances[type].instances.length;
								}

								$("td.version_instance_count[data-version-id=\"" + version.id + "\"]").html(
			                    	"<a href=\"/version/" + version.id + "\">"
			                    	+ instance_total + " instance(s) of "
			                    	+ Object.keys(instance_data.instances).length + " type(s)"
			                    	+ "</a>"
			                    );
							}
						});
					});

					$('.loading-overlay').remove();
					pm.stats.routerstats.redraw();
				}
			});
		}

	};
}());

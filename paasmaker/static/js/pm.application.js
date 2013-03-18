/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.application.js - interface for viewing an application and its versions
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.application = (function() {

	return {

		processVersionData: function(versions, data) {
			var processed_versions = [];

			var modifier = function(version) {
				version.health_string = '';

				if (version.health.overall && version.health.overall == 'OK') {
					version.health_string += version.health.overall;
				} else {
					for (var instance_type in version.health.types) {
						var h = version.health.types[instance_type];
						if (h.state != 'OK') {
							version.health_string += instance_type + ': ' + h.state;
							if (h.message) {
								version.health_string += ' - ' + h.message;
							}
							version.health_string += '<br>';
						}
					}
				}

				version.buttons_to_show = {
					register: (version.state == 'PREPARED'),
					start: (version.state == 'READY' || version.state == 'PREPARED'),
					stop: (version.state == 'RUNNING'),
					deregister: (version.state == 'READY'),
					makecurrent: (version.state == 'RUNNING' && !version.is_current),
					delete: (version.state == 'PREPARED' && !version.is_current)
				};

				// replicate the behaviour of nice_state(); TODO: icons etc?
				version.state = version.state[0] + version.state.substr(1).toLowerCase();

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

		switchTo: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			if ($('#app_menu_wrapper a').length && $('#app_view_main').length) {
				$('#app_view_main').empty();
			} else {
				$('#main').empty();
				$('#main').append(
					$("<div id=\"app_menu_wrapper\">"),
					$("<div id=\"app_view_main\" class=\"with-application-list\">")
				);
				pm.history.loadingOverlay("#app_view_main");
			}

			pm.data.api({
				endpoint: 'application/' + url_match[1],	// or just document.location?
				callback: function(data) {
					pm.workspace.updateAppMenu(data.application.workspace_id);

					data.versions = pm.application.processVersionData(data.versions, data);
					if (data.current_version) {
						data.current_version = pm.application.processVersionData(data.current_version, data);
					}

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

					// render main template body (but with empty tables)
					$('#app_view_main').html(pm.handlebars.application_versions(data));

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

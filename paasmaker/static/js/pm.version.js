/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.application.js - interface for viewing an application and its versions
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.version = (function() {

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
				endpoint: 'version/' + url_match[1],	// or just document.location?
				callback: function(data) {
					pm.data.api({
						endpoint: 'application/' + data.version.application_id,
						callback: function(app_data) {
							pm.workspace.updateAppMenu(app_data.application.workspace_id);
						}
					});

					if (data.version.source_package_type && data.version.source_package_type == 'devdirectory') {
						// when the dev directory plugin is enabled, show some additional details
						data.version.using_dev_directory_plugin = true;
					}

					// render main template body (but with empty tables)
					$('#app_view_main').html(pm.handlebars.version_view(data));


					// TODO: permissions are also checked in template, but without workspace ID
					// if (pm.util.hasPermission('APPLICATION_VIEW_MANIFEST', workspace_id)) {
					$('#app_manifest_modal').on('show', function() {
						pm.data.template_from_api({
							endpoint: 'version/' + url_match[1] + '/manifest',
							template: pm.handlebars.version_manifest,
							element: '#app_manifest_modal .modal-body'
						});
					});

					pm.data.api({
						endpoint: 'version/' + url_match[1] + '/instances',
						callback: function(instance_data) {
							for (var type_name in instance_data.instances) {
								$('#app_view_main').append(pm.handlebars.version_instance_types(instance_data.instances[type_name]));
							}
						}
					});

					// add rows for each version from separate template file;
					// then fire off a separate API request to get instance counts
					// data.instance_types.forEach(function(version) {
					// 	$('table.all_versions').append(pm.handlebars.application_version_row(version));

					// 	pm.data.api({
					// 		endpoint: 'version/' + version.id + '/instances',
					// 		callback: function(instance_data) {
					// 			var instance_total = 0;
					// 			for (var type in instance_data.instances) {
					// 				instance_total += instance_data.instances[type].instances.length;
					// 			}

					// 			$("td.version_instance_count[data-version-id=\"" + version.id + "\"]").html(
			  //                   	"<a href=\"/version/" + version.id + "\">"
			  //                   	+ instance_total + " instance(s) of "
			  //                   	+ Object.keys(instance_data.instances).length + " type(s)"
			  //                   	+ "</a>"
			  //                   );
					// 		}
					// 	});
					// });

					$('.loading-overlay').remove();
					pm.stats.routerstats.redraw();
				}
			});
		}

	};
}());

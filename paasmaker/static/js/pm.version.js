/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.application.js - interface for viewing an application and its versions
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.version = (function() {

	return {
	
		processInstanceData: function(instance_array) {
			var processed_instances = [];

			instance_array.forEach(function(instance) {
				instance.created_moment = pm.util.parseDate(instance.created);
				instance.updated_moment = pm.util.parseDate(instance.updated);
				
				processed_instances.push(instance);
			});
			
			return processed_instances;
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

			pm.data.get_app_parents({
				version_id: url_match[1],
				callback: function(parents) {
					pm.workspace.updateAppMenu(parents.workspace.id, { version: url_match[1] });
					pm.application.updateBreadcrumbs(parents.workspace, parents.application, parents.version);
				}
			});

			pm.data.api({
				endpoint: 'version/' + url_match[1],	// or just document.location?
				callback: function(data) {
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
								instance_data.instances[type_name].instances = pm.version.processInstanceData(instance_data.instances[type_name].instances)
							
								$('#app_view_main').append(pm.handlebars.version_instance_types(instance_data.instances[type_name]));
							}

							// after rendering instances, add event handlers for viewing logs
							$('.instance-log-container').each(function(i, element) {
									new pm.logs.instance(streamSocket, $(element).attr('data-instance'));
							});
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

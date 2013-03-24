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
				callback: function(version_data) {
					if (version_data.version.source_package_type && version_data.version.source_package_type == 'devdirectory') {
						// when the dev directory plugin is enabled, show some additional details
						version_data.version.using_dev_directory_plugin = true;
					}

					// render main template body (but with empty tables)
					$('#app_view_main').html(pm.handlebars.version_view(version_data));

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
								var this_view = instance_data.instances[type_name];
							
								this_view.instances = pm.version.processInstanceData(this_view.instances);
								this_view.version_is_current = version_data.version.is_current;
								this_view.frontend_domain_postfix = version_data.frontend_domain_postfix;
							
								$('#app_view_main').append(pm.handlebars.version_instance_types(this_view));
							}

							// after rendering instances, add event handlers for viewing logs
							$('.instance-log-container').each(function(i, element) {
									new pm.logs.instance(streamSocket, $(element).attr('data-instance'));
							});
						}
					});

					$('.loading-overlay').remove();
					pm.stats.routerstats.redraw();
				}
			});
		}

	};
}());

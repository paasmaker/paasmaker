/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.version.js - interface for viewing a version and its running instances
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.version = (function() {

	return {

		processInstanceData: function(instance_array) {
			var processed_instances = [];

			instance_array.forEach(function(instance) {
				instance.created_moment = pm.util.formatDate(instance.created);
				instance.updated_moment = pm.util.formatDate(instance.updated);

				processed_instances.push(instance);
			});

			return processed_instances;
		},

		updateNodeNames: function() {
			var node_ids = {};
			$('a.version-instance-list-node').each(function(i, el) {
				node_ids[$(el).data('node-id')] = true;
			});
			for (var id in node_ids) {
				pm.data.api({
					endpoint: 'node/' + id,
					callback: function(node_data) {
						$('a.version-instance-list-node').each(function(i, el) {
							if ($(el).data('node-id') == node_data.node.id) {
								$(el).text(node_data.node.name)
							}
						});
					}
				});
			}
		},

		actionButton: function(e) {
			pm.history.loadingOverlay("#main_right_view");
			pm.data.post({
				endpoint: $(e.target).attr('href'),
				callback: function(data) {
					$('.loading-overlay').remove();
					// pushState so the Back button works, but TODO: this should be in pm.history?
					var url_match = document.location.pathname.match(/\/(\d+)\/?$/);
					window.history.pushState({ handle_in_js: true }, '', "/job/detail/" + data.job_id);
					pm.jobs.version_action.switchTo({ job_id: data.job_id, version_id: url_match[1] });
				}
			});
		},

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			pm.data.api({
				endpoint: 'version/' + url_match[1],	// or just document.location?
				callback: function(version_data) {
					if (version_data.version.source_package_type && version_data.version.source_package_type == 'devdirectory') {
						// when the dev directory plugin is enabled, show some additional details
						version_data.version.using_dev_directory_plugin = true;
					}

					version_data.version.health_string = pm.application.view.getHealthString(version_data.version);
					version_data.version.buttons_to_show = pm.application.view.getButtonMap(version_data.version);

					pm.data.get_app_parents({
						version_id: url_match[1],
						callback: function(parents) {

							// render main template body (but with empty tables); this needs to be done after
							// get_app_parents returns because permission checking needs the workspace ID
							version_data.workspace_id = parents.workspace.id;
							$('#main_right_view').html(pm.handlebars.version_view(version_data));

							// once the main template is rendered, fill in breadcrumbs and redraw the app menu
							pm.leftmenu.updateAppMenu(parents.workspace.id, { version: url_match[1] });
							pm.leftmenu.updateBreadcrumbs({
								workspace: parents.workspace,
								application: parents.application,
								version: parents.version
							});

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
										this_view.workspace_id = parents.workspace.id;

										$('#main_right_view').append(pm.handlebars.version_instance_types(this_view));
									}

									// after rendering instances: 
									// - set up expandable UUIDs and editable fields
									// - fetch node names from the API
									// - add event handlers for viewing instance logs
									pm.widgets.uuid.update();
									pm.widgets.editable.update();
									pm.version.updateNodeNames();
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
			});
		}

	};
}());

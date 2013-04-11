/* Paasmaker - Platform as a Service
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * pm.service.js - interface for importing and exporting services.
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.service) { pm.service = {}; }

pm.service.import_service = (function() {
	return {
		switchTo: function() {
			pm.leftmenu.redrawContainers();
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			pm.data.api({
				endpoint: '/service/' + url_match[1],
				callback: function(data) {
					// re-render menu and breadcrumbs
					pm.data.get_app_parents({
						application_id: data.service.application_id,
						callback: function(parents) {
							// Render the main area.
							$('#main_right_view').html(Handlebars.templates.service_import(data));

							pm.leftmenu.updateAppMenu(parents.workspace.id, { application_id: data.service.application_id });
							pm.leftmenu.updateBreadcrumbs({
								workspace: parents.workspace,
								application: parents.application,
								version: parents.version
							});

							// Init the uploader widget.
							$('.file-uploader-widget').each(function(i, element) {
								new pm.widgets.upload($(element), parents.workspace.id);
							});
						}
					});
				}
			});
		},

		actionButton: function(e) {
			pm.history.loadingOverlay("#main_right_view");
			var parent_form = $(e.target).parents('form');
			pm.data.post({
				endpoint: $(e.target).attr('href'),
				body_data: $(parent_form).serialize(),
				callback: function(data) {
					if(data.data.job_id) {
						$('.loading-overlay').remove();
						// pushState so the Back button works, but TODO: this should be in pm.history?
						var url_match = document.location.pathname.match(/\/(\d+)\/?$/);
						window.history.pushState({ handle_in_js: true }, '', "/job/detail/" + data.data.job_id);
						pm.jobs.single.switchTo({ job_id: data.data.job_id, application_id: data.data.application_id });
					}
				}
			});
		}
	};
}());

pm.service.export_service = (function() {
	return {
		switchTo: function() {
			pm.leftmenu.redrawContainers();
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			pm.data.api({
				endpoint: '/service/' + url_match[1],
				callback: function(data) {
					// Render the main area.
					$('#main_right_view').html(Handlebars.templates.service_export(data));

					// re-render menu and breadcrumbs
					pm.data.get_app_parents({
						application_id: data.service.application_id,
						callback: function(parents) {
							pm.leftmenu.updateAppMenu(parents.workspace.id, { application_id: data.service.application_id });
							pm.leftmenu.updateBreadcrumbs({
								workspace: parents.workspace,
								application: parents.application,
								version: parents.version
							});
						}
					});
				}
			});
		}
	};
}());
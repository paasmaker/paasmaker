/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.workspace = (function() {

	return {

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			
			var url_match = document.location.pathname.match(/\/(\d+)\//);
			pm.leftmenu.updateAppMenu(url_match[1]);
			
			pm.data.api({
				endpoint: 'workspace/' + url_match[1],	// or just document.location?
				callback: function(data) {
					$('#main_right_view').html(pm.handlebars.workspace_main(data));
					$('.loading-overlay').remove();
					pm.stats.workspace.redraw();

					pm.data.api({
						endpoint: 'job/list/workspace/' + url_match[1],
						callback: function(job_data) {
							pm.jobs.summary.show($('.workspace-overview .job-overview'), job_data.jobs.slice(0,5));
						}
					});
				}
			});
		}

	};
}());

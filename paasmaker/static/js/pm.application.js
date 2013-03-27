/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.application.js - interface for viewing an application and its versions
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.application) { pm.application = {}; }

pm.application.view = (function() {

	return {

		getButtonMap: function(version) {
			return {
				register: (version.state == 'PREPARED'),
				start: (version.state == 'READY' || version.state == 'PREPARED'),
				stop: (version.state == 'RUNNING'),
				deregister: (version.state == 'READY'),
				makecurrent: (version.state == 'RUNNING' && !version.is_current),
				delete: ((version.state == 'PREPARED' || version.state == 'NEW') && !version.is_current)
			};
		},

		getHealthString: function(version) {
			var health_string = '';

			if (version.health) {
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
			} else {
				health_string = "WARNING";
			}

			return health_string;
		},

		processVersionData: function(versions, data) {
			var processed_versions = [];

			var modifier = function(version) {
				version.health_string = pm.application.view.getHealthString(version);
				version.buttons_to_show = pm.application.view.getButtonMap(version);

				// replicate the behaviour of nice_state(); TODO: icons etc?
				version.display_state = version.state[0] + version.state.substr(1).toLowerCase();

				processed_versions.push(version);
			};

			if (typeof versions.length == 'number' && versions.length > 0) {
				versions.forEach(modifier);
				return processed_versions;
			}
			if (typeof versions.length == 'undefined') {
				modifier(versions);
				return processed_versions[0];
			}
		},

		actionButton: function(e) {
			pm.history.loadingOverlay("#main_right_view");
			pm.data.post({
				endpoint: $(e.target).attr('href'),
				callback: function(data) {
					if(data.job_id) {
						$('.loading-overlay').remove();
						// pushState so the Back button works, but TODO: this should be in pm.history?
						window.history.pushState({ handle_in_js: true }, '', "/job/detail/" + data.job_id);
						pm.jobs.single.switchTo({ job_id: data.job_id, version_id: $(e.target).data('version-id') });
					} else {
						pm.application.view.switchTo();
					}
				}
			});
		},

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

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

					data.versions = pm.application.view.processVersionData(data.versions, data);
					if (data.current_version) {
						data.current_version = pm.application.view.processVersionData(data.current_version, data);
					}

					// render main template body (but with empty tables)
					$('#main_right_view').html(Handlebars.templates.application_versions(data));

					// re-render menu and breadcrumbs
					pm.data.get_app_parents({
						application_id: url_match[1],
						callback: function(parents) {
							pm.leftmenu.updateAppMenu(parents.workspace.id, { application_id: url_match[1] });
							pm.leftmenu.updateBreadcrumbs({
								workspace: parents.workspace,
								application: parents.application,
								version: parents.version
							});
						}
					});

					// add rows for each version from separate template file;
					// then fire off a separate API request to get instance counts
					if (data.current_version) {
						$('table.current_version').append(Handlebars.templates.application_version_row(data.current_version));
					}
					data.versions.forEach(function(version) {
						$('table.all_versions').append(Handlebars.templates.application_version_row(version));

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


pm.application.services = (function() {

	return {

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			var url_match = document.location.pathname.match(/\/(\d+)\/services\/?$/);

			pm.data.api({
				endpoint: 'application/' + url_match[1] + '/services',	// or just document.location?
				callback: function(data) {
					for (var i = 0; i < data.services.length; i++) {
						if (data.services[i].credentials) {
							data.services[i].credentials_text = JSON.stringify(data.services[i].credentials, undefined, 4);
						}
					}

					pm.data.get_app_parents({
						application_id: url_match[1],
						callback: function(parents) {
							data.application = parents.application;
							$('#main_right_view').html(Handlebars.templates.application_services(data));

							pm.leftmenu.updateAppMenu(parents.workspace.id, { application_id: url_match[1] });
							pm.leftmenu.updateBreadcrumbs({
								workspace: parents.workspace,
								application: parents.application,
								suffix: "Services"
							});

							$('.loading-overlay').remove();
						}
					});
				}
			});
		}

	};
}());

/* Paasmaker - Platform as a Service
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * pm.admin.js - interface for administration pages
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.admin = {};

pm.admin.profile = (function() {
	return {
		switchTo: function() {
			pm.data.template_from_api({
				endpoint: 'profile',
				element: '#main',
				template: Handlebars.templates.user_profile
			});
		}
	};
}());

pm.admin.plugins = (function() {
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'configuration/plugins',
				callback: function(data) {
					var valid_plugins = [];

					for (var key in data.plugins) {
						var item = data.plugins[key];
						if (item.modes.indexOf('JOB') === -1) {
							if (Object.keys(item.options).length > 0) {
								item.options = JSON.stringify(item.options, undefined, 4);
							} else {
								item.options = '';
							}

							valid_plugins.push(item);
						}
					}

					$('#main').html(Handlebars.templates.configuration_plugins({ plugins: valid_plugins }));
				}
			});
		}
	};
}());

pm.admin.config_dump = (function() {
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'configuration/dump',
				callback: function(data) {
					var config_string = JSON.stringify(data.configuration, undefined, 4);

					$('#main').html(Handlebars.templates.configuration_dump({ configuration: config_string }));
				}
			});
		}
	};
}());

pm.admin.user_list = (function() {
	// TODO: this does not respect permissions for creating or editing users
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'user/list',
				callback: function(data) {
					for (var i=0; i < data.users.length; i++) {
						data.users[i].created_moment = pm.util.formatDate(data.users[i].created);
						data.users[i].updated_moment = pm.util.formatDate(data.users[i].updated);
					}

					$('#main').html(Handlebars.templates.user_list(data));
				}
			});
		}
	};
}());

pm.admin.role_list = (function() {
	// TODO: this does not respect permissions for creating or editing roles
	return {
		switchTo: function() {
			pm.data.template_from_api({
				endpoint: 'role/list',
				element: '#main',
				template: Handlebars.templates.role_list
			});
		}
	};
}());

pm.admin.allocation_list = (function() {
	return {
		switchTo: function() {
			pm.data.template_from_api({
				endpoint: 'role/allocation/list',
				element: '#main',
				template: Handlebars.templates.role_allocation_list
			});
		}
	};
}());

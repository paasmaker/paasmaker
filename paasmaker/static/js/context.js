define([
	'jquery',
	'underscore',
	'backbone',
	'socketio',
	'moment',
	'collections/workspaces',
	'collections/nodes',
	'collections/users',
	'collections/roles',
	'collections/roleallocations',
	'collections/applications',
	'collections/versions',
	'models/usermeta'
], function($, _, Backbone,
	moment,
	socketio,
	WorkspaceCollection,
	NodeCollection,
	UserCollection,
	RoleCollection,
	RoleAllocationCollection,
	ApplicationCollection,
	VersionCollection,
	UserMetadataModel
) {
	var module = {};
	module.dispatcher = _.clone(Backbone.Events);
	module.workspaces = new WorkspaceCollection();
	module.applications = new ApplicationCollection();
	module.versions = new VersionCollection();
	module.nodes = new NodeCollection();
	module.users = new UserCollection();
	module.roles = new RoleCollection();
	module.roleallocations = new RoleAllocationCollection();

	module.navigate = function(url) {
		module.router.navigate(url, {trigger: true});
	};

	module.hasPermission = function(permission, workspace_id, table) {
		// From the given table, figure out if the user has that
		// permission or not.
		// permission: the string permission name.
		// workspace_id: if supplied, should be an integer that is the
		//   workspace ID to limit the request to.
		// table: an object of values from the server.

		if(!table) {
			// Use the server-supplied permissions table.
			table = permissions;
		}

		var testKeys = [];
		if(workspace_id) {
			testKeys.push('' + workspace_id + '_' + permission);
		}
		testKeys.push('None_' + permission);

		for(var i = 0; i < testKeys.length; i++) {
			if(table[testKeys[i]]) {
				return true;
			}
		}

		return false;
	};

	module.initialize = function() {
		// Load the workspaces from the containing page.
		module.workspaces.reset(workspaces);
		// Load the user metadata from the containing page.
		module.usermeta = new UserMetadataModel(usermeta);
	};

	module.loadPlugin = function(pluginName, callback, errback) {
		var moduleName = 'plugin/' + pluginName + '/script'
		require([moduleName], function(loadedPlugin) {
			var completedInit = function() {
				if (callback) {
					callback(loadedPlugin);
				}
			};

			// Have we already loaded it? If so, we would have set a
			// called_name attribute on the module.
			if(!loadedPlugin._called_name) {
				// Load the CSS as well. This might 404 but that's ok.
				var cssPath = '/plugin/' + pluginName + '/stylesheet.css';
				$('head').append('<link href="' + cssPath + '" rel="stylesheet">');

				// Get the module to initalize itself.
				loadedPlugin._called_name = pluginName;
				loadedPlugin._resource_path = '/plugin/' + pluginName + '/';

				loadedPlugin.initialize(loadedPlugin._called_name, loadedPlugin._resource_path, completedInit);
			} else {
				completedInit();
			}
		}, errback);
	};

	module.getScmListSimple = function(pluginName, success, error) {
		var url = "/scm/list/repos?plugin=" + pluginName;
		$.ajax({
			url: url,
			dataType: 'json',
			success: function(data) {
				if (data.error && data.error.length > 0) {
					error({}, data);
				} else {
					success(data.data.repositories);
				}
			},
			error: error
		});
	};

	return module;
});
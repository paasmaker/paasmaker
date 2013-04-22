define([
	'jquery',
	'underscore',
	'backbone',
	'router',
	'collections/workspaces'
], function($, _, Backbone, Router, WorkspaceCollection) {
	var module = {};
	module.dispatcher = _.clone(Backbone.Events);
	module.workspaces = new WorkspaceCollection();

	module.router = new Router();
	// TODO: Workaround to get the context into the router.
	module.router.context = module;

	module.initialize = function() {
		module.workspaces.fetch();
	};

	module.loadPlugin = function(pluginName, callback) {
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
		});
	};

	return module;
});
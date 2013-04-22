define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'views/workspace/header'
], function($, _, Backbone, Context, WorkspaceHeaderView) {
	var module = {};

	module.initialize = function() {
		Context.router.initialize();
		Context.initialize();

		// Set up the header workspace list.
		var headerWorkspaceViewList = new WorkspaceHeaderView({
			collection: Context.workspaces,
			el: $('.nav .workspace-list')
		});

		// Kick off the controllers.
		// CAUTION: This ends control of this function.
		Backbone.history.start({pushState: true});
	};

	return module;
});
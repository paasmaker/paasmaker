define([
	'jquery',
	'underscore',
	'backbone'
], function($, _, Backbone){
	var AppRouter = Backbone.Router.extend({
		initialize: function() {
			this.route('', "overview");
			this.route(/^workspace\/(\d+)\/applications$/, 'applicationList');
			this.route('workspace/create', 'workspaceCreate');
		},

		overview: function() {
			// this.context.loadPlugin('paasmaker.service.mysql', function(mod) {
			// });
		},

		workspaceCreate: function() {
			console.log('Workspace create');
		},

		applicationList: function(workspace_id) {
			console.log("Application list");
			console.log(workspace_id);
		},

		defaultAction: function(args) {
			console.log('Default!');
			console.log(args);
		}
	});

	return AppRouter;
});
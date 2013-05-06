define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var VersionModel = Backbone.Model.extend({
		defaults: {
			version: 0,
		},
		url: function() {
			return '/version/' + this.id + '?format=json';
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				var intermediary = data.data.version;
				intermediary.application = data.data.application;
				intermediary.workspace = data.data.workspace;
				return intermediary;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},
		canRegister: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				this.attributes.state == 'PREPARED';
		},
		canStart: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				(this.attributes.state == 'READY' || this.attributes.state == 'PREPARED');
		},
		canStop: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				this.attributes.state == 'RUNNING';
		},
		canDeregister: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				this.attributes.state == 'READY';
		},
		canMakeCurrent: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				this.attributes.state == 'RUNNING' &&
				!this.attributes.is_current;
		},
		canDelete: function(context) {
			return context.hasPermission('APPLICATION_DEPLOY', this.attributes.workspace.id) &&
				(this.attributes.state == 'PREPARED' || this.attributes.state == 'NEW') &&
				!this.attributes.is_current;
		}
	});

	return VersionModel;
});
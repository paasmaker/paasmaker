define([
	'underscore',
	'backbone',
	'collections/applications'
], function(_, Backbone, ApplicationCollection){
	var WorkspaceModel = Backbone.Model.extend({
		defaults: {
			name: "None",
			stub: "none"
		},
		initialize: function() {
			this.applications = new ApplicationCollection();
			this.applications.url = '/workspace/' + this.id + '/applications?format=json';
		}
	});

	return WorkspaceModel;
});
define([
	'underscore',
	'backbone',
	'collections/applications'
], function(_, Backbone, ApplicationCollection){
	var WorkspaceModel = Backbone.Model.extend({
		defaults: {
			name: "",
			stub: "",
			tags: {}
		},
		initialize: function() {
			this.applications = new ApplicationCollection();
			this.applications.url = '/workspace/' + this.id + '/applications?format=json';
		},
		url: function() {
			if (this.id) {
				return '/workspace/' + this.id + '?format=json';
			} else {
				return '/workspace/create?format=json'
			}
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.workspace;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},
	});

	return WorkspaceModel;
});
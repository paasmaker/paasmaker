define([
	'underscore',
	'backbone',
	'collections/versions'
], function(_, Backbone, VersionCollection){
	var ApplicationModel = Backbone.Model.extend({
		defaults: {
			name: "none",
		},
		initialize: function() {
			this.versions = new VersionCollection();
		},
		url: function() {
			return '/application/' + this.id + '?format=json';
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				var intermediary = data.data.application;
				intermediary.versions = data.data.versions;
				intermediary.workspace = data.data.workspace;
				intermediary.instance_counts = data.data.instance_counts;
				return intermediary;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		}
	});

	return ApplicationModel;
});
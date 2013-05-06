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
		}
	});

	return VersionModel;
});
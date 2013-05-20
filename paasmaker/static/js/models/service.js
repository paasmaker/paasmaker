define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var ServiceModel = Backbone.Model.extend({
		defaults: {
			name: "",
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				var intermediary = data.data.service;
				intermediary.workspace = data.data.workspace;
				intermediary.application = data.data.application;
				return intermediary;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},
	});

	return ServiceModel;
});
define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var NodeModel = Backbone.Model.extend({
		defaults: {
			name: "none",
			uuid: "none"
		},
		url: function() {
			return '/node/' + this.id + '?format=json';
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.node;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		}
	});

	return NodeModel;
});
define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var RoleModel = Backbone.Model.extend({
		defaults: {
			name: "",
			permissions: []
		},
		url: function() {
			if (this.id) {
				return '/role/' + this.id + '?format=json';
			} else {
				return '/role/create?format=json'
			}
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.role;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		}
	});

	return RoleModel;
});
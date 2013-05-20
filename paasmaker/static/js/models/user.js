define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var UserModel = Backbone.Model.extend({
		defaults: {
			name: "",
			login: "",
			email: "",
			enabled: true,
			password: ""
		},
		url: function() {
			if (this.id) {
				return '/user/' + this.id + '?format=json';
			} else {
				return '/user/create?format=json'
			}
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.user;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		}
	});

	return UserModel;
});
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
		},
		sync: function(method, model, options) {
			if(method === 'create' || method === 'update') {
				// Wrap the values into the "data" section of the request.
				options.attrs = {data: model.toJSON(options)};
			}
			Backbone.sync(method, model, options);
		}
	});

	return UserModel;
});
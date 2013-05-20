define([
	'underscore',
	'backbone',
	'models/user'
], function(_, Backbone, UserModel){
	var UserCollection = Backbone.Collection.extend({
		model: UserModel,
		url: '/user/list?format=json',
		parse: function(response) {
			return response.data.users;
		}
	});

	return UserCollection;
});
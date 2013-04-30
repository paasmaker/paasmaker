define([
	'underscore',
	'backbone',
	'models/role'
], function(_, Backbone, RoleModel){
	var RoleCollection = Backbone.Collection.extend({
		model: RoleModel,
		url: '/role/list?format=json',
		parse: function(response) {
			return response.data.roles;
		}
	});

	return RoleCollection;
});
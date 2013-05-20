define([
	'underscore',
	'backbone',
	'models/roleallocation'
], function(_, Backbone, RoleAllocationModel){
	var RoleAllocationCollection = Backbone.Collection.extend({
		model: RoleAllocationModel,
		url: '/role/allocation/list?format=json',
		parse: function(response) {
			return response.data.allocations;
		}
	});

	return RoleAllocationCollection;
});
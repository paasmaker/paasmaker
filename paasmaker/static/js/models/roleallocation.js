define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var RoleAllocationModel = Backbone.Model.extend({
		defaults: {
			workspace_id: null,
			user_id: null,
			role_id: null
		},
		url: function() {
			if (this.id) {
				return '/role/allocation/unassign?format=json';
			} else {
				return '/role/allocation/assign?format=json'
			}
		}
	});

	return RoleAllocationModel;
});
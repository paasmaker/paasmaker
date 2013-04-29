define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var AdministrationModel = Backbone.Model.extend({
		defaults: {
			name: "none",
			path: "/none",
			active: false,
		}
	});

	return AdministrationModel;
});
define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var InstanceModel = Backbone.Model.extend({
		defaults: {
			name: "none",
			uuid: "none"
		},
	});

	return InstanceModel;
});
define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var NodeModel = Backbone.Model.extend({
		defaults: {
			name: "none",
			uuid: "none"
		}
	});

	return NodeModel;
});
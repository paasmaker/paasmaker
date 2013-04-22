define([
	'underscore',
	'backbone'
], function(_, Backbone){
	var ApplicationModel = Backbone.Model.extend({
		defaults: {
			name: "none",
		}
	});

	return ApplicationModel;
});
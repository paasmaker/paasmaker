define([
	'underscore',
	'backbone',
	'models/workspace'
], function(_, Backbone, ApplicationModel){
	var ApplicationCollection = Backbone.Collection.extend({
		model: ApplicationModel
	});

	return ApplicationCollection;
});
define([
	'underscore',
	'backbone',
	'models/administration'
], function(_, Backbone, AdministrationModel){
	var AdministrationCollection = Backbone.Collection.extend({
		model: AdministrationModel
	});

	return AdministrationCollection;
});
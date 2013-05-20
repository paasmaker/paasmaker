define([
	'underscore',
	'backbone',
	'models/instance'
], function(_, Backbone, InstanceModel){
	var InstanceCollection = Backbone.Collection.extend({
		model: InstanceModel,
		parse: function(response) {
			return response.data.instances;
		}
	});

	return InstanceCollection;
});
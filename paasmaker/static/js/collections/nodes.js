define([
	'underscore',
	'backbone',
	'models/node'
], function(_, Backbone, NodeModel){
	var NodeCollection = Backbone.Collection.extend({
		model: NodeModel,
		url: '/node/list?format=json',
		parse: function(response) {
			return response.data.nodes;
		}
	});

	return NodeCollection;
});
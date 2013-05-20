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
		},
		stateClasses: {
			'ACTIVE': { badge: 'badge-success', icon: 'icon-ok' },
			'STOPPED': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'INACTIVE': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'DOWN': { badge: 'badge-important', icon: 'icon-ban-circle' }
		}
	});

	return NodeCollection;
});
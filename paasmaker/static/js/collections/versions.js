define([
	'underscore',
	'backbone',
	'models/version'
], function(_, Backbone, VersionModel){
	var VersionCollection = Backbone.Collection.extend({
		model: VersionModel,
		parse: function(response) {
			return response.data.versions;
		},
		healthClasses: {
			'OK': { badge: 'badge-success', icon: 'icon-ok' },
			'WARNING': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'ERROR': { badge: 'badge-important', icon: 'icon-ban-circle' }
		}
	});

	return VersionCollection;
});
define([
	'underscore',
	'backbone',
	'models/application'
], function(_, Backbone, ApplicationModel){
	var ApplicationCollection = Backbone.Collection.extend({
		model: ApplicationModel,
		healthClasses: {
			'OK': { badge: 'badge-success', icon: 'icon-ok' },
			'WARNING': { badge: 'badge-warning', icon: 'icon-warning-sign' },
			'ERROR': { badge: 'badge-important', icon: 'icon-ban-circle' }
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.applications;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},
		comparator: function(application) {
			return application.get("name");
		}
	});

	return ApplicationCollection;
});
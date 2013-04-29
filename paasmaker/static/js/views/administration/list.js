define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/list.html'
], function($, _, Backbone, context, Bases, AdministrationListTemplate){
	var AdministationListView = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html(AdministrationListTemplate({
				administrations: this.collection.models,
				context: context
			}));
		},
		events: {
			"click a": "navigateAway"
		}
	});

	return AdministationListView;
});
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/sidebar.html'
], function($, _, Backbone, context, Bases, AdministrationSidebarTemplate){
	var AdministationSidebarView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('change', this.render, this);
			this.render();
		},
		render: function() {
			this.$el.html(AdministrationSidebarTemplate({
				administrations: this.collection.models,
				context: context
			}));
		},
		events: {
			"click a": "navigateAway"
		}
	});

	return AdministationSidebarView;
});
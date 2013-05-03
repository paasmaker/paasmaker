define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/administration/router-dump.html'
], function($, _, Backbone, context, Bases, util, RouterDumpTemplate){
	var RouterDumpView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(Bases.errorLoadingHtml + '<h1>Loading...</h1>');

			this.startLoadingFull();
		},
		dataReady: function(data) {
			this.doneLoading();
			this.routerTable = data.data;
			this.render();
		},
		render: function() {
			this.$el.html(RouterDumpTemplate({
				context: context,
				table: this.routerTable
			}));
			util.shrinkUuids(this.$el);
		},
		events: {
			"click a.instances": "expandInstances",
			"click a.nodes": "expandNodes",
			"click a.routes": "expandRoutes"
		},
		expandInstances: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var target = $('div.instances', el.parent());
			target.slideToggle();
		},
		expandNodes: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var target = $('div.nodes', el.parent());
			target.slideToggle();
		},
		expandRoutes: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var target = $('div.routes', el.parent());
			target.slideToggle();
		}
	});

	return RouterDumpView;
});
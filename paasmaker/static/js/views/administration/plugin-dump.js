define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/administration/plugin-dump.html'
], function($, _, Backbone, context, Bases, util, PluginDumpTemplate){
	var PluginDumpView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(Bases.errorLoadingHtml + '<h1>Loading...</h1>');

			this.startLoadingFull();
		},
		dataReady: function(data) {
			this.doneLoading();
			this.plugins = data.data;
			console.log(this.plugins);
			this.render();
		},
		render: function() {
			this.$el.html(PluginDumpTemplate({
				context: context,
				plugins: this.plugins,
				_: _
			}));
		},
		events: {
			"click a.configuration": "expandConfiguration"
		},
		expandConfiguration: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var target = $('pre.configuration', el.parent());
			target.slideToggle();
		}
	});

	return PluginDumpView;
});
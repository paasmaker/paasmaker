define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/administration/configuration-dump.html'
], function($, _, Backbone, context, Bases, util, ConfigurationDumpTemplate){
	var ConfigurationDumpView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(Bases.errorLoadingHtml + '<h1>Loading...</h1>');

			this.startLoadingFull();
		},
		dataReady: function(data) {
			this.doneLoading();
			this.configuration = data.data;
			this.render();
		},
		render: function() {
			this.$el.html(ConfigurationDumpTemplate({
				context: context,
				configuration: this.configuration
			}));
		}
	});

	return ConfigurationDumpView;
});
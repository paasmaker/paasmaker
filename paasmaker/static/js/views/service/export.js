define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/service/export.html'
], function($, _, Backbone, context, Bases, ServiceExportTemplate){
	var ServiceExportView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(
				Bases.errorLoadingHtml + '<h1>Loading...</h1>'
			);
			this.startLoadingFull();

			this.exportPlugin = null;
			this.exportPluginInstance = null;

			// Attempt to load the plugin for this service.
			var _self = this;
			context.loadPlugin(this.model.attributes.provider, function(mod) {
				_self.exportPlugin = mod;
				_self.render();
			}, function(error) {
				// This isn't an error, it just means that the plugin has
				// no options interface.
				_self.render();
			});
		},
		gotPlugin: function() {
			this.doneLoading();
		},
		destroy: function() {
			// Destroy the plugin, if loaded.
			if (this.exportPluginInstance) {
				this.exportPluginInstance.destroy();
			}

			// And undelegate events.
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(Bases.errorLoadingHtml + ServiceExportTemplate({
				service: this.model,
				context: context,
				_: _
			}));

			var pluginInner = this.$('.export-inner');
			if (this.exportPlugin && this.exportPlugin.SERVICE_EXPORT) {
				// Instantiate it.
				this.exportPluginInstance = new this.exportPlugin.SERVICE_EXPORT({
					el: pluginInner,
					service: this.model
				});
			} else {
				pluginInner.text("This plugin has no options.");
			}

			return this;
		}
	});

	return ServiceExportView;
});
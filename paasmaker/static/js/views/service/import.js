define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'views/widget/fileupload',
	'tpl!templates/service/import.html'
], function($, _, Backbone, context, Bases, FileUploadView, ServiceImportTemplate){
	var ServiceImportView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(
				Bases.errorLoadingHtml + '<h1>Loading...</h1>'
			);
			this.startLoadingFull();

			this.importPlugin = null;
			this.importPluginInstance = null;
			this.uploader = null;

			// Attempt to load the plugin for this service.
			var _self = this;
			context.loadPlugin(this.model.attributes.provider, function(mod) {
				_self.importPlugin = mod;
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
			if (this.importPluginInstance) {
				this.importPluginInstance.destroy();
			}
			if (this.uploader) {
				this.uploader.destroy();
			}

			// And undelegate events.
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(Bases.errorLoadingHtml + ServiceImportTemplate({
				service: this.model,
				context: context,
				_: _
			}));

			var pluginInner = this.$('.import-inner');
			if (this.importPlugin && this.importPlugin.SERVICE_IMPORT) {
				// Instantiate it.
				this.importPluginInstance = new this.importPlugin.SERVICE_IMPORT({
					el: pluginInner,
					service: this.model
				});
			} else {
				pluginInner.text("This plugin has no options.");
			}

			this.uploader = new FileUploadView({
				workspace_id: this.model.attributes.workspace.id,
				el: this.$('.file-uploader-widget')
			});

			return this;
		},
		events: {
			"click button.submit": "submit"
		},
		submit: function(e) {
			e.preventDefault();

			// Figure out what options we're going to pass to the server.
			if (this.$('input[name=uploaded_file]').length == 0) {
				this.$('.alert').text("No file uploaded.");
				this.$('.alert').show();
				return;
			} else {
				var parameters = {};
				parameters.uploaded_file = this.$('input[name=uploaded_file]').val();

				// Get the plugin to add it's options.
				if (this.importPluginInstance) {
					parameters = this.importPluginInstance.serialize(parameters);

					if (typeof parameters == 'string') {
						// Something went wrong.
						this.$('.alert').html(parameters);
						this.$('.alert').show();
						return;
					}
				}

				var _self = this;
				this.startLoadingFull();
				$.ajax({
					url: '/service/import/' + this.model.id + '?format=json',
					type: 'POST',
					dataType: 'json',
					data: JSON.stringify({
						data: parameters
					}),
					success: function(data) {
						_self.doneLoading();

						context.navigate('/service/import/' + _self.model.id + '/' + data.data.job_id);
					},
					error: _.bind(this.loadingError, this)
				});
			}
		}
	});

	return ServiceImportView;
});
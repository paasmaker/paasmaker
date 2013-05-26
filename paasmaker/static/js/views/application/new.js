define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/application/new.html'
], function($, _, Backbone, context, Bases, ApplicationNewTemplate){
	var ApplicationNewView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(
				Bases.errorLoadingHtml + '<h1>Loading...</h1>'
			);
			this.startLoadingFull();

			this.scmPlugins = {};
			this.scmInstances = {};

			// Load the list of available SCMs, and last version data.
			// The caller will supply us with a URL.
			$.ajax({
				url: this.options.url,
				dataType: 'json',
				success: _.bind(this.gotNewMetadata, this),
				error: _.bind(this.loadingError, this)
			});
		},
		gotNewMetadata: function(data) {
			this.metadata = data.data;
			this.scms = data.data.scms;
			this.scmsToLoad = data.data.scms.length;

			// Now load the SCM plugins.
			var _self = this;
			_.each(this.scms, function(element, index, list) {
				context.loadPlugin(element.plugin, function(mod) {
					_self.gotScmPlugin(element.plugin, mod);
				}, _.bind(_self.pluginError, _self))
			});
		},
		pluginError: function(err) {
			this.doneLoading();
			this.$('h1').remove();
			this.$('.alert').show();
			this.$('.alert').html("Error loading plugin " + err.requireModules[0] + ": " + err.message + ". This is probably a programming error with the plugin.");
		},
		gotScmPlugin: function(name, plugin) {
			this.scmPlugins[name] = plugin;
			this.scmsToLoad -= 1;

			if (this.scmsToLoad <= 0) {
				this.render();
			}
		},
		destroy: function() {
			// Destroy any SCM views.
			_.each(this.scmInstances, function(value, key, list) {
				value.destroy();
			});

			// And undelegate events.
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(Bases.errorLoadingHtml + ApplicationNewTemplate({
				plugins: this.scms,
				context: context,
				newApplication: this.options.newApplication,
				_: _
			}));

			// Set up the bootstrap tabs.
			if (!this.metadata.last_scm_name) {
				this.$('.nav-tabs a:first').tab('show');
			}

			// Get each plugin to set up it's own view.
			var _self = this;
			_.each(this.scms, function(scm, index, list) {
				var container = _self.$('#export-' + index + ' .scm-inner');
				var view = new _self.scmPlugins[scm.plugin].SCM_EXPORT({
					el: container,
					workspace: _self.options.workspace
				});
				_self.scmInstances[scm.plugin] = view;

				// Select the tab, if this was the last used SCM.
				if (_self.metadata.last_scm_name && _self.metadata.last_scm_name == scm.plugin) {
					_self.$('.nav-tabs a.export-' + index).tab('show');

					// Reload the parameters.
					view.loadParameters(_self.metadata.last_scm_params);

					// Reset the manifest path from last time.
					if (_self.metadata.last_scm_params && _self.metadata.last_scm_params.manifest_path) {
						$('input[name=manifest_path]', container.parent()).val(_self.metadata.last_scm_params.manifest_path);
					}
				}

				// Set up any SCM listers for this SCM.
				_.each(scm.listers, function(lister, index, list) {
					context.loadPlugin(lister.plugin, function(listerPluginModule) {
						// Create a box for the SCM lister.
						var listerContainer = $('<div class="tile scm-list"><img src="/static/img/load-inline.gif" width="16" height="11" alt="Loading..." /></div>');
						var allListers = $('.scm-listers', container.parent());
						allListers.append(listerContainer);

						_self.scmInstances[lister.plugin] = new listerPluginModule.SCM_LIST({
							el: listerContainer,
							title: lister.title,
							plugin: lister.plugin,
							selectedCallback: function(values) {
								// Get all the controls on the form.
								// The plugin should give us "parameters.location"
								// and so forth, and we look for an populate all those.
								var inputs = $('select, input', container);

								_.each(values, function(scmValue, scmKeyName, list) {
									_.each(inputs, function(input, index, list) {
										input = $(input);
										if (input.attr('name') == scmKeyName) {
											input.val(scmValue);
										}
									});
								});
							}
						});

					}, _.bind(_self.pluginError, _self))
				});
			});

			return this;
		},
		events: {
			"click .nav-tabs a": "tabSelect",
			"click a.submit": "submit"
		},
		tabSelect: function(e) {
			e.preventDefault();
			$(e.currentTarget).tab('show');
		},
		submit: function(e) {
			e.preventDefault();
			this.$('.alert').hide();
			var button = $(e.currentTarget);
			// TODO: This is a little fragile; if the new form is
			// rearranged, it stops working.
			var scmForm = button.parent().parent().parent();
			var scmName = $('input[name=scm]', scmForm).val();

			// Ask the view to serialize itself.
			var data = this.scmInstances[scmName].serialize();

			if (typeof data == 'string') {
				// Something went wrong.
				this.$('.alert').html(data);
				this.$('.alert').show();
			} else {
				// Add in the common data.
				data.scm = scmName;
				data.manifest_path = $('input[name=manifest_path]', scmForm).val();

				this.startLoadingFull();
				$.ajax({
					url: this.options.url,
					dataType: 'json',
					method: 'POST',
					data: JSON.stringify({data: data}),
					success: _.bind(this.startNewVersionSuccess, this),
					error: _.bind(this.loadingError, this)
				});
			}
		},
		startNewVersionSuccess: function(data) {
			this.doneLoading();
			if (this.options.newApplication) {
				context.navigate('/workspace/' + this.options.workspace.id + '/applications/new/' + data.data.job_id);
			} else {
				context.navigate('/application/' + this.options.application.id + '/newversion/' + data.data.job_id);
			}
		}
	});

	return ApplicationNewView;
});
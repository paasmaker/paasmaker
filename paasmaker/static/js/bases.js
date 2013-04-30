define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'tpl!templates/layout/loadingerror.html'
], function($, _, Backbone,
	context,
	loadingErrorTemplate
) {
	var module = {};

	module.errorLoadingHtml = loadingErrorTemplate();

	module.BaseView = Backbone.View.extend({
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));

			e.preventDefault();
		},
		startLoadingInline: function() {
			this.$('.loading').show();
			this.$('.error').hide();
		},
		startLoadingFull: function() {
			var overlay = $('<div class="loading-overlay"><img src="/static/img/spinner32.gif" alt=""></div>');
			this.$el.append(overlay);
			overlay.animate({ opacity: 0.8 });
		},
		doneLoading: function() {
			this.$('.loading').hide();
			this.$('.loading-overlay').remove();
		},
		loadingError: function(model, xhr, options) {
			this.doneLoading();
			this.$('.alert').show();
			var lineOne = $("<strong></strong>");
			var lineTwo = '';
			var lineThree = '';
			var errorText = "";
			if (xhr.status) {
				errorText += xhr.status + ' ';
			}
			if (xhr.statusText) {
				errorText += xhr.statusText + ' ';
			}
			if (errorText.length > 0) {
				lineOne.text(errorText);
			}
			if (xhr.responseText) {
				try {
					var parsed = JSON.parse(xhr.responseText);
					lineThree = $('<ul></ul>');

					if (parsed.data && parsed.data.input_errors) {
						_.each(parsed.data.input_errors, function(value, key, list) {
							var errorEl = $('<li></li>');
							errorEl.text(key + ': ' + value);
							lineThree.append(errorEl);
						});
					} else if (parsed.errors) {
						_.each(parsed.errors, function(element, index, list) {
							var errorEl = $('<li></li>');
							errorEl.text(element);
							lineThree.append(errorEl);
						});
					}
				} catch (e) {
					// Couldn't parse it as JSON.
					lineTwo = $('<pre></pre>');
					lineTwo.text(xhr.responseText);
				}
			}
			if (xhr.errors) {
				lineThree = $('<ul></ul>');
				_.each(xhr.errors, function(element, index, list) {
					var errorEl = $('<li></li>');
					errorEl.text(element);
					lineThree.append(errorEl);
				});
			}
			this.$('.alert').empty();
			this.$('.alert').append(lineOne);
			this.$('.alert').append(lineTwo);
			this.$('.alert').append(lineThree);
		},
		destroy: function() {
			// Override in your class.
		}
	});

	return module;
});
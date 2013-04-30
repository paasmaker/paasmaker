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
			var errorText = "";
			if (xhr.status) {
				errorText += xhr.status + ' ';
			}
			if (xhr.statusText) {
				errorText += xhr.statusText + ' ';
			}
			if (xhr.responseText) {
				errorText += xhr.responseText;
			}
			this.$('.alert').text(errorText);
		},
		destroy: function() {
			// Override in your class.
		}
	});

	return module;
});
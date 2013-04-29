define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/loadingerror.html'
], function($, _, Backbone,
	loadingErrorTemplate
) {
	var module = {};

	module.errorLoadingHtml = loadingErrorTemplate();

	module.BaseView = Backbone.View.extend({
		navigateAway: function(e) {
			context.navigate($(e.currentTarget).attr('href'));

			e.preventDefault();
		},
		startLoading: function() {
			this.$('.loading').show();
			this.$('.error').hide();
		},
		doneLoading: function() {
			this.$('.loading').hide();
		},
		loadingError: function(model, xhr, options) {
			this.doneLoading();
			this.$('.error').show();
			this.$('.error .contents').text(xhr.status + ' ' + xhr.statusText + ': ' + xhr.responseText)
		}
	});

	return module;
});
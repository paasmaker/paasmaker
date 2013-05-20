define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, context, Bases){
	var GenericLoadingView = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html(
				Bases.errorLoadingHtml + '<h1>Loading...</h1>'
			);
			this.startLoadingFull();
		},
		loadingError: function(model, xhr, options) {
			this.$('h1').remove();
			// Call the parent loadingError().
			Bases.BaseView.prototype.loadingError.apply(this, [model, xhr, options]);
		}
	});

	return GenericLoadingView;
});
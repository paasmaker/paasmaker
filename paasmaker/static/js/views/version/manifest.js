define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/version/manifest.html'
], function($, _, Backbone, context, Bases, VersionManifestTemplate){
	var VersionManifestView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html('<h1>Loading...</h1>');
		},
		destroy: function() {
		},
		dataReady: function(data) {
			this.data = data.data;
			this.render();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(VersionManifestTemplate({
				manifest: this.data,
				context: context
			}));

			return this;
		}
	});

	return VersionManifestView;
});
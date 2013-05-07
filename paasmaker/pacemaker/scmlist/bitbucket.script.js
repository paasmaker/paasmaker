define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/layout/scmlister-default.html'
], function($, _, Backbone, context, Bases, ScmListerDefaultTemplate) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		callback();
	};

	module.SCM_LIST = Bases.BaseView.extend({
		initialize: function() {
			console.log(this.$el);
			this.$el.html(
				ScmListerDefaultTemplate({
					title: this.options.title,
					repositories: []
				})
			);

			// Fetch our repositories.
			context.getScmListSimple(
				this.options.plugin,
				_.bind(this.gotScmList, this),
				_.bind(this.loadingError, this)
			);
		},
		gotScmList: function(repositories) {
			this.repositories = repositories;
			this.render();
		},
		loadingError: function(model, xhr, options) {
			this.$el.empty();
			this.$el.html('<div class="alert alert-error"></div>');

			Bases.BaseView.prototype.loadingError.apply(this, [model, xhr, options]);
		},
		render: function() {
			this.$el.html(ScmListerDefaultTemplate({
				title: this.options.title,
				repositories: this.repositories
			}));
		},
		events: {
			"change select": "selectedRepository"
		},
		selectedRepository: function(e) {
			var el = $(e.currentTarget);
			this.options.selectedCallback({'parameters.location': el.val()});
		},
		destroy: function() {
		}
	});

	return module;
});
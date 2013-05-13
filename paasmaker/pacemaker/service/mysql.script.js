
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, context, Bases) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		var toLoad = 2;

		function doneLoading() {
			toLoad -= 1;
			if (toLoad <= 0) {
				callback();
			}
		}

		require(['tpl!' + resourcePath + 'export.html'], function(template) {
			module.exportTemplate = template;
			doneLoading();
		});

		require(['tpl!' + resourcePath + 'import.html'], function(template) {
			module.importTemplate = template;
			doneLoading();
		});
	};

	module.SERVICE_EXPORT = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html(module.exportTemplate());
			this.$el.addClass('well');
			this.$el.addClass('well-small');
		}
	});

	module.SERVICE_IMPORT = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html(module.importTemplate());
			this.$el.addClass('well');
			this.$el.addClass('well-small');
		},
		serialize: function(parameters) {
			return parameters;
		}
	});

	return module;
});
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, Context, Bases) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		require(['tpl!' + resourcePath + 'scm_export.html'], function(template) {
			module.exportTemplate = template;
			callback();
		});
	};

	module.SCM_EXPORT = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html(module.exportTemplate());
		},
		serialize: function() {
			var location = this.$('input.git-location').val();
			if (location == "") {
				return "You must specify a Git location.";
			} else {
				return {
					parameters: {
						location: this.$('input.git-location').val(),
						branch: this.$('input.git-branch').val(),
						revision: this.$('input.git-revision').val()
					}
				};
			}
		},
		loadParameters: function(previousData) {
			if (previousData.location) {
				this.$('input.git-location').val(previousData.location);
			}
			if (previousData.branch) {
				this.$('input.git-branch').val(previousData.branch);
			}
		}
	});

	return module;
});
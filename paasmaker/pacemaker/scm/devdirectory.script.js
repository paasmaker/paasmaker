define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, Context, Bases) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		callback();
	};

	module.SCM_EXPORT = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html('<div class="control-group"><label class="control-label" for="devdir-location">Local Directory:</label><div class="controls"><input type="text" name="parameters.location" id="devdir-location" class="devdir-location" required="required" /></div></div>');
		},
		serialize: function() {
			var location = this.$('input.devdir-location').val();
			if (location == "") {
				return "You must specify a directory.";
			} else {
				return {
					parameters: {
						location: this.$('input.devdir-location').val()
					}
				};
			}
		},
		loadParameters: function(previousData) {
			if (previousData.location) {
				this.$('.devdir-location').val(previousData.location);
			}
		}
	});

	return module;
});
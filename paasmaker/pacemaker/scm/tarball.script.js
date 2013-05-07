define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'views/layout/fileupload'
], function($, _, Backbone, Context, Bases, FileUploadView) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		callback();
	};

	module.SCM_EXPORT = Bases.BaseView.extend({
		initialize: function() {
			this.render();
		},
		render: function() {
			this.$el.html('<div class="control-group"><label class="control-label">Upload file:</label><div class="controls"><div class="file-uploader-widget"></div></div></div>');

			this.uploader = new FileUploadView({
				workspace_id: this.options.workspace.id,
				el: this.$('.file-uploader-widget')
			});
		},
		serialize: function() {
			if (this.$('input[name=uploaded_file]').length == 0) {
				return "No file uploaded.";
			} else {
				return {
					uploaded_file: this.$('input[name=uploaded_file]').val()
				};
			}
		},
		loadParameters: function(previousData) {
			// No parameters to reset.
		},
		destroy: function() {
			this.uploader.destroy();
		}
	});

	return module;
});
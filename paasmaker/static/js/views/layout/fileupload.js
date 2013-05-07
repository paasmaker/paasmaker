define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/layout/fileupload.html',
	'resumable'
], function($, _, Backbone, context, Bases, FileUploadTemplate, Resumable){
	var FileUploaderView = Bases.BaseView.extend({
		initialize: function() {
			if (!context.hasPermission('FILE_UPLOAD', this.options.workspace_id)) {
				this.$el.html('<p>Sorry, you need the FILE_UPLOAD permission to upload here.</p>');
			} else {
				this.render();
			}
		},
		render: function() {
			this.$el.html(FileUploadTemplate());

			this.resumable = new Resumable(
				{
					chunkSize: 1*512*1024,
					target: '/files/upload',
					fileParameterName: 'file.data'
				}
			);

			this.resumable.assignBrowse(this.$('a.btn'));
			this.resumable.assignDrop(this.$('.drop'));

			var _self = this;
			this.resumable.on('fileAdded', function(file) {
				_self.$('.status').html(file.fileName + ', ' + file.size + ' bytes');
				_self.resumable.upload();

				// Hide the drop container when uploading starts
				// TODO: this prevents retrying after failure
				_self.$('.drop').hide();
				_self.$('.status').show();
			});
			this.resumable.on('fileSuccess', function(file, message) {
				// Parse the message.
				var contents = $.parseJSON(message);
				// Create a hidden form element with the uploaded identifier.
				var hiddenEl = $('<input type="hidden" name="uploaded_file" />');
				hiddenEl.attr('value', contents.data.identifier);
				_self.$el.append(hiddenEl);
				_self.$('.status').html("Upload complete.");
			});
			this.resumable.on('fileError', function(file, message) {
				var contents = $.parseJSON(message);
				var errorList = $('<ul class="error"></ul>');
				for(var i = 0; i < contents.errors.length; i++)
				{
					var error = $('<li></li>');
					error.text(contents.errors[i]);
					errorList.append(error);
				}
				_self.$('.status').html(errorList);
			});
			this.resumable.on('progress', function(file) {
				_self.$('progress').val(_self.resumable.progress() * 100);
			});
		},
		destroy: function() {
			// Make sure we don't keep retrying uploads
			// after the user leaves the page.
			if (this.resumable.isUploading()) {
				this.resumable.cancel();
			}
		}
	});

	return FileUploaderView;
});
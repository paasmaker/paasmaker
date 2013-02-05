
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.widgets) { pm.widgets = {}; }

pm.widgets.upload = function(container)
{
	this.container = container;

	this.upButton = $('<a href="#">Upload</a>');
	this.dropContainer = $('<div class="drop"></div>');

	this.dropContainer.append(this.upButton);
	this.container.append(this.dropContainer);

	this.statusArea = $('<div class="status"></div>');
	this.container.append(this.statusArea);
	this.progress = $('<progress value="0" max="100" />');
	this.container.append(this.progress);

	this.resumable = new Resumable(
		{
			target: '/files/upload',
			fileParameterName: 'file.data'
		}
	);

	this.resumable.assignBrowse(this.upButton);
	this.resumable.assignDrop(this.dropContainer);

	var _self = this;
	this.resumable.on('fileAdded', function(file){
		_self.statusArea.html(file.fileName + ', ' + file.size + ' bytes');
		_self.resumable.upload();
	});
	this.resumable.on('fileSuccess', function(file, message){
		// Parse the message.
		var contents = $.parseJSON(message);
		// Create a hidden form element with the uploaded identifier.
		var hiddenEl = $('<input type="hidden" name="uploaded_file" />');
		hiddenEl.attr('value', contents.data.identifier);
		_self.container.append(hiddenEl);
		_self.statusArea.html("Upload complete.");
		// Hide the drop container.
		_self.dropContainer.hide();
	});
	this.resumable.on('fileError', function(file, message){
		var contents = $.parseJSON(message);
		var errorList = $('<ul class="error"></ul>');
		for(var i = 0; i < contents.errors.length; i++)
		{
			var error = $('<li></li>');
			error.text(contents.errors[i]);
			errorList.append(error);
		}
		_self.statusArea.html(errorList);
	});
	this.resumable.on('progress', function(file){
		_self.progress.val(_self.resumable.progress() * 100);
	});
}

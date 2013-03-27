
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.widgets) { pm.widgets = {}; }


/**
 * Very simple handler utility to display shortened version of SHA1 UUIDs
 * (e.g. for instances or nodes); relies on the element starting out empty
 * and the full UUID being stored in the title attribute.
 */
pm.widgets.uuid = {
	update: function() {
		$('code.uuid-shrink').each(function(i, el) {
			el = $(el);
			if (el.text().length == 0) {
				el.text(el.attr('title').substr(0,8));
				el.on('click', pm.widgets.uuid.clickHandler);
			}
		});
	},

	clickHandler: function(e) {
		el = $(e.target);
		if (el.text().length > 8) {
			el.text(el.attr('title').substr(0,8));
		} else {
			el.text(el.attr('title'));
		}
	}
}


/**
 * Simple inline editor widget, for creating a quick-alter interface around display
 * values (e.g. instance type quantity). The element with class="editable" must have
 * data attributes for "editable-type", "value", and "endpoint", as well as a child
 * link/button with class="editable-button".
 * When the button is clicked, creates a Bootstrap popover with input field and submit
 * button that will send an ajax POST (with serialised key-value pair) to the endpoint.
 */
pm.widgets.editable = (function(){
	var templates = {
		text_field_form: Handlebars.compile(
			"<form action=\"{{endpoint}}\" method=\"post\""
				+ " class=\"editable-field-form input-append\">"
				+ "<input name=\"{{key}}\" type=\"text\" value=\"{{value}}\">"
				+ "<button class=\"btn\">Save</button>"
				+ "</form>")
	};

	return {
		definitions: {
			"instance-type-quantity": {
				key: "quantity",
				title: "Number of instances to run",
				content: templates.text_field_form
			}
		},

		update: function() {
			$('.editable').each(function(i, el) {
				el = $(el);
				if (el.data('editable-type') && el.data('value') && el.data('endpoint')
						&& $('a.editable-button', el).length) {

					var definition = pm.widgets.editable.definitions[el.data('editable-type')];
					el.popover({
						html: true,
						title: definition.title,
						content: definition.content({
							key: definition.key, value: el.data('value'), endpoint: el.data('endpoint')
						})
					});

					$('a.editable-button', el).on('click', pm.widgets.editable.clickHandler);
				}
			});
		},

		clickHandler: function(e) {
			e.preventDefault();
			var container = $(e.target).parents('.editable');
			container.popover('toggle');
		}
	}
}());


pm.widgets.upload = function(container)
{
	this.container = container;

	this.upButton = $('<a class="btn" href="#"><i class="icon-upload"></i> Upload File</a>');
	this.dropContainer = $('<div class="drop"></div>');

	this.dropContainer.append(this.upButton);
	this.container.append(this.dropContainer);

	this.statusArea = $('<div class="status"></div>');
	this.statusArea.hide();
	this.container.append(this.statusArea);

	this.progress = $('<progress value="0" max="100" />');
	this.container.append(this.progress);

	this.resumable = new Resumable(
		{
			chunkSize: 1*512*1024,
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

		// Hide the drop container when uploading starts
		// TODO: this prevents retrying after failure
		_self.dropContainer.hide();
		_self.statusArea.show();
	});
	this.resumable.on('fileSuccess', function(file, message){
		// Parse the message.
		var contents = $.parseJSON(message);
		// Create a hidden form element with the uploaded identifier.
		var hiddenEl = $('<input type="hidden" name="uploaded_file" />');
		hiddenEl.attr('value', contents.data.identifier);
		_self.container.append(hiddenEl);
		_self.statusArea.html("Upload complete.");
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

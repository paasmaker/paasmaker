
var SimpleTagEditor = function(form, container)
{
	this.form = form;
	this.container = container;
	this.editarea = $('.editor', container);
	this.outputarea = $('.output', container);

	var _self = this;
	var addButton = $('<a href="#">Add...</a>');
	addButton.click(
		function(e)
		{
			var newRow = $('<div class="pair"></div>');
			newRow.append($('<input type="text" class="tag" />'));
			newRow.append($('<input type="text" class="value" />'));
			_self.editarea.append(newRow);
			_self.addRemoveButtons();

			e.preventDefault();
		}
	);

	this.container.append(addButton);
	/*var buildButton = $('<a href="#">Build...</a>');
	buildButton.click(function(e){_self.rebuildOutput()});
	this.container.append(buildButton);*/
	this.addRemoveButtons();

	// When the form is submitted, add our inputs.
	$(form).submit(
		function(e)
		{
			_self.rebuildOutput()
		}
	);
}

SimpleTagEditor.prototype.addRemoveButtons = function()
{
	// Find rows without a remove button.
	var rows = $('.pair', this.editarea).not('.has-remove');
	rows.each(
		function(index, element)
		{
			var el = $(element);
			var removeButton = $('<a href="#">Remove</a>');
			removeButton.click(
				function(e)
				{
					// Remove it from the DOM.
					el.remove();

					e.preventDefault();
				}
			);
			el.addClass('has-remove');
			el.append(removeButton);
		}
	);
}

SimpleTagEditor.prototype.rebuildOutput = function()
{
	var rows = $('.pair', this.editarea);
	this.outputarea.empty();
	var _self = this;
	rows.each(
		function(index, element)
		{
			var el = $(element);
			var tag = $('.tag', el).val();
			var value = $('.value', el).val();

			var tagEl = $('<input type="hidden" />');
			tagEl.attr({name: 'tags.' + tag, value: value});

			_self.outputarea.append(tagEl);
		}
	);
}

var FileUploader = function(container)
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

var JobRootStreamHandler = function(container)
{
	this.container = container;
	this.job_id = container.attr('data-job');

	var _self = this;
	var ws = new WebSocket("ws://" + window.location.host + "/job/stream");
	ws.onopen = function() {
		ws.send($.toJSON({request: 'subscribe', data: {'job_id': _self.job_id}}));
	};
	ws.onmessage = function (evt) {
		var message = $.parseJSON(evt.data);
		console.log(message);
		switch(message.type)
		{
			case 'tree':
				_self.renderJobTree(_self.container, [message.data], 0);
				break;
			case 'subscribed':
				break;
			case 'status':
				_self.updateStatus(message.data);
				break;
		}
	};
}

JobRootStreamHandler.prototype.renderJobTree = function(container, tree, level)
{
	// Empty out the container.
	container.empty();

	// Sort my tree by time.
	tree.sort(function(a, b) {
		return a.time - b.time;
	});

	var _self = this;
	$.each(tree, function(index, element)
	{
		var thisContainer = _self.createContainer(element.job_id, level);
		container.append(thisContainer);
		$('.title', thisContainer).text(element.title);
		$('.state', thisContainer).text(element.state);
		// TODO: Have to switch states...
		// TODO: Fix this.
		var stateContainer = $('.state', thisContainer);
		stateContainer.removeClass('state-SUCCESS');
		stateContainer.removeClass('state-FAILED');
		stateContainer.removeClass('state-ABORTED');
		stateContainer.removeClass('state-WAITING');
		$('.state', thisContainer).addClass('state-' + element.state);

		// Recurse into the children.
		if( element.children )
		{
			var childContainer = $('.children', thisContainer);
			_self.renderJobTree(childContainer, element.children, level + 1);
		}
	});
}

JobRootStreamHandler.prototype.createContainer = function(job_id, level)
{
	var thisJobContainer = $('<div class="job-status level' + level + '"></div>');
	thisJobContainer.addClass(job_id);
	thisJobContainer.append($('<span class="title"></span>'));
	thisJobContainer.append($('<span class="state"></span>'));
	thisJobContainer.append($('<span class="children"></span>'));

	return thisJobContainer;
}

JobRootStreamHandler.prototype.updateStatus = function(status)
{
	// Find the appropriate status element.
	var el = $('.' + status.job_id + ' .state', this.container);
	el.text(status.state);
	// TODO: Fix this.
	el.removeClass('state-SUCCESS');
	el.removeClass('state-FAILED');
	el.removeClass('state-ABORTED');
	el.removeClass('state-WAITING');
	$('.state', this.container).addClass('state-' + status.state);
}

function testBrowserFeatures(resultContainer)
{
	resultContainer.empty();

	resultList = $('<ul></ul>');

	var reportResult = function(name, result)
	{
		resultLabel = result ? 'Success' : 'Failure';
		resultList.append($('<li>' + name + ': ' + resultLabel + '</li>'));
	}

	reportResult("Websockets", Modernizr.websockets);

	var r = new Resumable();

	reportResult("HTML5 File uploads", r.support);

	resultContainer.append(resultList);
}

$(document).ready(
	function()
	{
		if( $('.workspace-tag-editor').length > 0 )
		{
			var workspaceTagEditor = new SimpleTagEditor($('form'), $('.workspace-tag-editor'));
		}

		if( $('.test-browser-features').length > 0 )
		{
			testBrowserFeatures($('.test-browser-features'));
		}

		if( $('.file-uploader-widget').length > 0 )
		{
			$('.file-uploader-widget').each(
				function(index, element)
				{
					var uploader = new FileUploader($(element));
				}
			);
		}

		if( $('.job-root').length > 0 )
		{
			$('.job-root').each(
				function(index, element)
				{
					var jobStream = new JobRootStreamHandler($(element));
				}
			);
		}
	}
)
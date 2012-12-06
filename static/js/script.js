
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
	this.jobStatusRemote = new WebSocket("ws://" + window.location.host + "/job/stream");
	this.jobStatusRemote.onopen = function() {
		_self.jobStatusRemote.send($.toJSON({request: 'subscribe', data: {'job_id': _self.job_id}}));
	};
	this.jobStatusRemote.onmessage = function (evt) {
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
			case 'new':
				_self.newJob(_self.container, message.data);
				break;
		}
	};

	this.subscribedLogs = {};
	this.logStreamRemote = new WebSocket("ws://" + window.location.host + "/log/stream");
	this.logStreamRemote.onopen = function() {
		console.log("Connected to remote for log streaming.");
	};
	this.logStreamRemote.onmessage = function (evt) {
		var message = $.parseJSON(evt.data);
		console.log(message);
		switch(message.type)
		{
			case 'lines':
				_self.handleNewLines(message.data);
				break;
		}
	};
}

/*JobRootStreamHandler.prototype.refreshTree = function(job_id)
{
	var message = $.toJSON({request: 'tree', data: {'job_id': job_id}});
	this.jobStatusRemote.send(message);
}*/

JobRootStreamHandler.prototype.toggleSubscribeLog = function(job_id, container)
{
	if( this.subscribedLogs[job_id] )
	{
		// Already subscribed.
		var message = $.toJSON({request: 'unsubscribe', data: {'job_id': job_id}});
		console.log(message);
		this.logStreamRemote.send(message);
		this.subscribedLogs[job_id] = false
	}
	else
	{
		var position = container.attr('data-position');
		if( !position )
		{
			position = 0;
		}

		// Not subscribed. Subscribe.
		var message = $.toJSON({request: 'subscribe', data: {'job_id': job_id, 'position': position}});
		console.log(message);
		this.logStreamRemote.send(message);
		this.subscribedLogs[job_id] = true
	}
}

JobRootStreamHandler.prototype.handleNewLines = function(message)
{
	var container = $('.' + message.job_id + ' .log');
	container.append(message.lines.join(''));
	container.attr('data-position', message.position);
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
		var thisContainer = _self.createContainer(element.job_id, level, element);
		container.append(thisContainer);
	});
}

JobRootStreamHandler.prototype.newJob = function(container, data)
{
	// Find the parent container.
	var parentId = data['parent_id'];
	var parentChildContainer = $('.children-' + parentId);
	var levelParent = parseInt(parentChildContainer.parent().attr('data-level'), 10) + 1;
	var newJobContainer = this.createContainer(data.job_id, levelParent, data);
	parentChildContainer.append(newJobContainer);
}

JobRootStreamHandler.prototype.createContainer = function(job_id, level, data)
{
	var thisJobContainer = $('<div class="job-status level' + level + '"></div>');
	thisJobContainer.attr('data-level', level);

	var details = $('<div class="details"></div>');
	details.addClass(job_id);
	details.append($('<span class="title"></span>'));
	details.append($('<span class="toolbox"></span>'));
	details.append($('<span class="state"></span>'));
	details.append($('<span class="time"></span>'));
	details.append($('<div class="log"></div>'));
	thisJobContainer.append(details);

	var childrenContainer = $('<div class="children"></div>');
	childrenContainer.addClass('children-' + job_id);
	thisJobContainer.append(childrenContainer);

	$('.title', thisJobContainer).text(data.title);
	$('.state', thisJobContainer).text(data.state);
	/*var thisTime = new Date();
	thisTime.setTime(data.time * 1000);
	$('.time', thisJobContainer).text(thisTime.toString());*/
	// TODO: Have to switch states...
	// TODO: Fix this.
	var stateContainer = $('.state', thisJobContainer);
	stateContainer.removeClass('state-SUCCESS');
	stateContainer.removeClass('state-FAILED');
	stateContainer.removeClass('state-ABORTED');
	stateContainer.removeClass('state-WAITING');
	stateContainer.addClass('state-' + data.state);
	var logContainer = $('.log', thisJobContainer);

	var toolbox = $('.toolbox', thisJobContainer);
	var _self = this;
	if( false == toolbox.hasClass('populated') )
	{
		// Populate and hook up the toolbox.
		var logExpander = $('<a href="#"><i class="icon-list"></i></a>');
		logExpander.click(
			function(e)
			{
				logContainer.slideToggle();
				_self.toggleSubscribeLog(data.job_id, logContainer);

				e.preventDefault();
			}
		);
		toolbox.append(logExpander);
		toolbox.addClass('populated');
	}

	// Recurse into the children.
	if( data.children )
	{
		var childContainer = $('.children', thisJobContainer);
		_self.renderJobTree(childContainer, data.children, level + 1);
	}

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
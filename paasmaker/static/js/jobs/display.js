
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.jobs) { pm.jobs = {}; }

pm.jobs.display = function(container, streamSocket)
{
	this.container = container;
	this.streamSocket;
	this.job_id = container.attr('data-job');
	this.logSubscribed = {};

	var _self = this;

	// Subscribe to the events we want.
	this.streamSocket = streamSocket;
	this.streamSocket.on('job.tree',
		function(job_id, tree)
		{
			if(_self.job_id == job_id)
			{
				_self.renderJobTree([tree], 0);
			}
		}
	);

	this.streamSocket.on('job.new',
		function(data)
		{
			_self.newJob(data);
		}
	);

	this.streamSocket.on('job.status',
		function(job_id, status)
		{
			_self.updateStatus(status);
		}
	);

	this.streamSocket.on('log.lines',
		function(job_id, lines, position)
		{
			if(_self.logSubscribed[job_id])
			{
				_self.handleNewLines(job_id, lines, position);
			}
		}
	);

	this.streamSocket.on('log.zerosize',
		function(job_id)
		{
			if(_self.logSubscribed[job_id])
			{
				_self.handleZeroSizeLog(job_id);
			}
		}
	);

	_self.streamSocket.emit('job.subscribe', _self.job_id);
}

pm.jobs.display.prototype.handleZeroSizeLog = function(job_id)
{
	var container = $('.' + job_id + ' .log', this.container);
	container.html("No log entries for this job.")
	container.addClass('no-data');
}

pm.jobs.display.prototype.isScrolledToBottom = function(el) {
	var content_height = el[0].scrollHeight;
	var current_view_bottom = el[0].scrollTop + el.innerHeight();
	return (content_height == current_view_bottom);
}

pm.jobs.display.prototype.handleNewLines = function(job_id, lines, position)
{
	var container = $('.' + job_id + ' .log', this.container);
	container.removeClass('no-data');
	var formatted = this.formatLogLines(lines.join(''));

	if (this.isScrolledToBottom(container)) { var reset_scroll = true; }

	container.append(formatted);
	container.attr('data-position', position);

	if (reset_scroll) {
		// TODO: test this across browsers
		container[0].scrollTop = container[0].scrollHeight;
	}
}

pm.jobs.display.prototype.renderJobTree = function(tree, level, container)
{
	// Empty out the container.
	var workingContainer = this.container;
	if( container )
	{
		workingContainer = container;
	}
	workingContainer.empty();

	// Sort my tree by time.
	tree.sort(function(a, b) {
		return a.time - b.time;
	});

	var _self = this;
	$.each(tree, function(index, element)
	{
		var thisContainer = _self.createContainer(element.job_id, level, element);
		workingContainer.append(thisContainer);
	});
}

pm.jobs.display.prototype.newJob = function(data)
{
	// Find the parent container.
	var parentId = data['parent_id'];
	var parentChildContainer = $('.children-' + parentId, this.container);
	var levelParent = parseInt(parentChildContainer.parent().attr('data-level'), 10) + 1;
	var newJobContainer = this.createContainer(data.job_id, levelParent, data);
	parentChildContainer.append(newJobContainer);
}

pm.jobs.display.prototype.createContainer = function(job_id, level, data)
{
	var thisJobContainer = $('<div class="job-status level' + level + '"></div>');
	thisJobContainer.attr('data-level', level);

	var details = $('<div class="details clearfix"></div>');
	details.addClass(job_id);
	details.append($('<span class="state"></span>'));
	details.append($('<span class="toolbox"></span>'));
	details.append($('<span class="title"></span>'));
	details.append($('<span class="summary"></span>'));
	// details.append($('<span class="time"></span>'));
	details.append($('<pre class="log"></pre>'));
	thisJobContainer.append(details);

	var childrenContainer = $('<div class="children"></div>');
	childrenContainer.addClass('children-' + job_id);
	thisJobContainer.append(childrenContainer);

	var title = data.title;
	if (/[0-9T\-\:\.]{26}/.test(title)) {
		// TODO: this is hackish, but for now the timestamp is embedded at the end of
		// the title string for each job; parse it out and reformat using moment.js
		var raw_date = title.substr(-26);
		var moment = pm.util.formatDate(raw_date);
		
		// remove old unformatted date, and "at" if present
		title = title.substring(0, title.length - 26);
		if (title.substr(-4) == " at ") { title = title.substring(0, title.length - 3); }
		title += " <span title=\"" + raw_date + "\">" + moment.calendar + "</span>";
	}
	$('.title', thisJobContainer).html(title);
	
	if( data.summary && data.state != 'SUCCESS' )
	{
		$('.summary', thisJobContainer).text('Summary: ' + data.summary);
	}
	else
	{
		$('.summary', thisJobContainer).text('');
	}

	/*var thisTime = new Date();
	thisTime.setTime(data.time * 1000);
	$('.time', thisJobContainer).text(thisTime.toString());*/

	var stateContainer = $('.state', thisJobContainer);
	this.setStateClass(stateContainer, data.state);
	this.setStateIcon(stateContainer, data.state);
	var logContainer = $('.log', thisJobContainer);

	var toolbox = $('.toolbox', thisJobContainer);
	var _self = this;
	if( false == toolbox.hasClass('populated') )
	{
		// Populate and hook up the toolbox.
		var logExpander = $('<a href="#" title="View log for this job"><i class="icon-list"></i></a>');
		logExpander.click(
			function(e)
			{
				_self.toggleSubscribeLog(data.job_id, logContainer);

				e.preventDefault();
			}
		);
		toolbox.append(logExpander);

		if( data.state != 'SUCCESS' && data.state != 'FAILED' && data.state != 'ABORTED' )
		{
			var aborter = $('<a class="aborter" href="#" title="Abort Job"><i class="icon-off"></i></a>');
			aborter.click(
				function(e)
				{
					$.getJSON(
						'/job/abort/' + job_id + '?format=json',
						function( data )
						{
							// No action to date.
							console.log(data);
						}
					);
					e.preventDefault();
				}
			);
			toolbox.append(aborter);
		}

		toolbox.addClass('populated');
	}

	// Recurse into the children.
	if( data.children )
	{
		var childContainer = $('.children', thisJobContainer);
		_self.renderJobTree(data.children, level + 1, childContainer);
	}

	return thisJobContainer;
}

BOOTSTRAP_CLASS_MAP = {
	'FAILED': 'important', // Er, ok.
	'ABORTED': 'warning',
	'SUCCESS': 'success',
	'WAITING': 'info',
	'RUNNING': 'primary'
}

BOOTSTRAP_ICON_MAP = {
	'FAILED': 'icon-remove',
	'ABORTED': 'icon-ban-circle',
	'SUCCESS': 'icon-ok',
	'WAITING': 'icon-time',
	'RUNNING': 'icon-loading',
	'NEW': 'icon-certificate'
}

pm.jobs.display.prototype.setStateClass = function(element, state)
{
	var oldState = element.attr('data-state');
	if( oldState )
	{
		element.removeClass('state-' + oldState);
		var oldBootstrapClass = BOOTSTRAP_CLASS_MAP[oldState];
		if( oldBootstrapClass )
		{
			element.removeClass('label-' + oldBootstrapClass);
		}
	}
	element.addClass('state-' + state);
	element.attr('data-state', state);

	// And add a class that inherits a bootstrap colour.
	var bootstrapClass = BOOTSTRAP_CLASS_MAP[state];
	if( !bootstrapClass )
	{
		bootstrapClass = 'default';
	}

	element.addClass('label');
	element.addClass('label-' + bootstrapClass);
}

pm.jobs.display.prototype.setStateIcon = function(element, state)
{
	var icon = $('<i></i>');

	var oldState = element.attr('data-state');
	if( oldState )
	{
		element.removeClass('state-' + oldState);
		var oldBootstrapClass = BOOTSTRAP_ICON_MAP[oldState];
		if( oldBootstrapClass )
		{
			element.removeClass('label-' + oldBootstrapClass);
		}
	}

	icon.addClass('icon-white');
	icon.addClass(BOOTSTRAP_ICON_MAP[state]);

	element.html(icon);
	var textual = $('<span></span>');
	textual.text(state);
	element.append(textual);
}

pm.jobs.display.prototype.updateStatus = function(status)
{
	// Find the appropriate status element.
	var el = $('.' + status.job_id + ' .state', this.container);
	this.setStateClass(el, status.state);
	this.setStateIcon(el, status.state);
	el.attr('data-state', status.state);

	if( status.state == 'SUCCESS' || status.state == 'FAILED' || status.state == 'ABORTED' )
	{
		// Remove the abort button, if present.
		$('.' + status.job_id + ' .aborter', this.container).remove();
	}

	if( status.summary && status.state != 'SUCCESS' )
	{
		var summaryEl = $('.' + status.job_id + ' .summary', this.container);
		summaryEl.text('Summary: ' + status.summary);
	}
}

pm.jobs.display.prototype.toggleSubscribeLog = function(job_id, container)
{
	if( this.logSubscribed[job_id] )
	{
		container.slideUp();
		this.streamSocket.emit('log.unsubscribe', job_id);
		this.logSubscribed[job_id] = false;
	}
	else
	{
		var position = container.attr('data-position');
		this.logSubscribed[job_id] = true;
		this.streamSocket.emit('log.subscribe', job_id, position);
		container.slideDown();
	}
}

// TODO: This is duplicated code. Refactor this so it isn't.
pm.jobs.display.prototype.formatLogLines = function(lines)
{
	var LOG_LEVEL_MAP = [
		['DEBUG', 'label'],
		['INFO', 'label label-info'],
		['WARNING', 'label label-warning'],
		['ERROR', 'label label-important'],
		['CRITICAL', 'label label-important']
	]

	var output = lines;
	output = htmlEscape(output);
	for( var i = 0; i < LOG_LEVEL_MAP.length; i++ )
	{
		output = output.replace(
			new RegExp('\\s' + LOG_LEVEL_MAP[i][0] + '\\s', 'g'),
			' <span class="' + LOG_LEVEL_MAP[i][1] + '">' + LOG_LEVEL_MAP[i][0] + '</span> '
		);
	}
	return output;
}
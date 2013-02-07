
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.logs) { pm.logs = {}; }

pm.logs.instance = function(streamSocket, instance_id)
{
	this.streamSocket = streamSocket;
	this.instance_id = instance_id;
	this.isSubscribed = false;

	// Set up the container.
	this.toggle = $('.toggle.' + instance_id);
	this.toggle.html($('<i class="icon-list"></i>'));
	this.container = $('.instance-log-container.' + instance_id);
	this.pre = $('<pre></pre>');
	this.container.hide();
	this.container.append(this.pre);

	var _self = this;
	this.toggle.click(
		function(e)
		{
			_self.toggleSubscribe();
			e.preventDefault();
		}
	);

	this.streamSocket.on('log.lines',
		function(job_id, lines, position)
		{
			if(job_id == _self.instance_id)
			{
				_self.handleNewLines(job_id, lines, position);
			}
		}
	);

	this.streamSocket.on('log.zerosize',
		function(job_id)
		{
			if(job_id == _self.instance_id)
			{
				_self.handleZeroSizeLog(job_id);
			}
		}
	);
}

pm.logs.instance.prototype.toggleSubscribe = function()
{
	if( this.isSubscribed )
	{
		this.container.slideUp();
		this.isSubscribed = false;
		this.streamSocket.emit('log.unsubscribe', this.instance_id);
	}
	else
	{
		this.isSubscribed = true;
		var position = this.pre.attr('data-position');
		this.streamSocket.emit('log.subscribe', this.instance_id, position);
		this.container.slideDown();
	}
}

pm.logs.instance.prototype.handleZeroSizeLog = function(job_id)
{
	this.pre.html("No log entries for this job.")
	this.pre.addClass('no-data');
}

pm.logs.instance.prototype.handleNewLines = function(job_id, lines, position)
{
	this.pre.removeClass('no-data');
	var formatted = this.formatLogLines(lines.join(''));
	this.pre.append(formatted);
	this.pre.attr('data-position', position);
}

// TODO: This is duplicated code. Refactor this so it isn't.
pm.logs.instance.prototype.formatLogLines = function(lines)
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
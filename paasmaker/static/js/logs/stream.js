
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.logs) { pm.logs = {}; }

pm.logs.stream = function(endpoint)
{
	// Call the parent.
	WebsocketHandler.call(this, "/log/stream");

	// And now set up other internal variables.
	this.subscriptions = [];
	this.handlers = {};

	// Connect.
	this.connect();
}

pm.logs.stream.prototype = new WebsocketHandler("/log/stream");
pm.logs.stream.prototype.constructor = pm.logs.stream;

pm.logs.stream.prototype.isSubscribed = function(job_id)
{
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		if( this.subscriptions[i] == job_id )
		{
			return true;
		}
	}

	return false;
}

pm.logs.stream.prototype.subscribe = function(job_id, displayHandler, position, startup)
{
	if(!position)
	{
		position = 0;
	}
	this.handlers[job_id] = displayHandler;
	if( !this.isSubscribed(job_id) )
	{
		this.subscriptions.push(job_id);
	}
	this.send({request: 'subscribe', data: {'job_id': job_id, 'position': position}});
}

pm.logs.stream.prototype.unsubscribe = function(job_id)
{
	// Remove from subscriptions.
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		if( this.subscriptions[i] == job_id )
		{
			this.subscriptions.splice(i, 1);
			break;
		}
	}

	this.send({request: 'unsubscribe', data: {'job_id': job_id}});
}

pm.logs.stream.prototype.onmessage = function(message)
{
	// Find a handler to work with it.
	var handler = this.handlers[message.data.job_id];

	switch(message.type)
	{
		case 'lines':
			handler.handleNewLines(this, message.data);
			break;
		case 'zerosize':
			handler.handleZeroSizeLog(this, message.data);
			break;
	}
}


pm.logs.stream.prototype.formatLogLines = function(lines)
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

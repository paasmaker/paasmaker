
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.logs) { pm.logs = {}; }

pm.logs.instance = function(logStream, instance_id)
{
	this.logStream = logStream;
	this.instance_id = instance_id;

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
}

pm.logs.instance.prototype.toggleSubscribe = function()
{
	if( this.logStream.isSubscribed(this.instance_id) )
	{
		this.container.slideUp();
		this.logStream.unsubscribe(this.instance_id);
	}
	else
	{
		var position = this.pre.attr('data-position');
		this.logStream.subscribe(this.instance_id, this, position);
		this.container.slideDown();
	}
}

pm.logs.instance.prototype.handleZeroSizeLog = function(stream, message)
{
	this.pre.html("No log entries for this job.")
	this.pre.addClass('no-data');
}

pm.logs.instance.prototype.handleNewLines = function(stream, message)
{
	this.pre.removeClass('no-data');
	var formatted = stream.formatLogLines(message.lines.join(''));
	this.pre.append(formatted);
	this.pre.attr('data-position', message.position);
}

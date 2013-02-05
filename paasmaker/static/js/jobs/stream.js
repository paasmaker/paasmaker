
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.jobs) { pm.jobs = {}; }

pm.jobs.stream = function(endpoint)
{
	// Call the parent.
	WebsocketHandler.call(this, "/job/stream");

	// And now set up other internal variables.
	this.handlers = {};

	// Connect.
	this.connect();
}

pm.jobs.stream.prototype = new WebsocketHandler("/job/stream");
pm.jobs.stream.prototype.constructor = pm.jobs.stream;

pm.jobs.stream.prototype.subscribe = function(job_id, displayHandler)
{
	this.handlers[job_id] = displayHandler;
	this.send({request: 'subscribe', data: {'job_id': job_id}});
}

pm.jobs.stream.prototype.onmessage = function(message)
{
	switch(message.type)
	{
		case 'tree':
			var handler = this.handlers[message.data.job_id];
			handler.renderJobTree([message.data], 0);
			break;
		case 'subscribed':
			break;
		case 'status':
			var handler = this.handlers[message.data.root_id];
			handler.updateStatus(message.data);
			break;
		case 'new':
			var handler = this.handlers[message.data.root_id];
			handler.newJob(message.data);
			break;
	}
}

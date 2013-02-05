
if (!window.pm) { var pm = {}; }	// TODO: module handling
pm.stats = {};

pm.stats.router = function(container)
{
	// Call the parent.
	WebsocketHandler.call(this, "/router/stats/stream");

	// And now set up other internal variables.
	this.container = container;
	this.input_name = container.attr('data-name');
	this.input_id = container.attr('data-inputid');

	var _self = this;
	this.ready = false;

	// For speed later, pre-lookup the value instances.
	this.requests = $('.stat-requests .value', container);
	this.bytes = $('.stat-bytes .value', container);
	this.time_average = $('.stat-time_average .value', container);
	this.onexx = $('.stat-1xx .value', container);
	this.twoxx = $('.stat-2xx .value', container);
	this.threexx = $('.stat-3xx .value', container);
	this.fourxx = $('.stat-4xx .value', container);
	this.fivexx = $('.stat-5xx .value', container);

	this.onexx_percentage = $('.stat-1xx_percentage .value', container);
	this.twoxx_percentage = $('.stat-2xx_percentage .value', container);
	this.threexx_percentage = $('.stat-3xx_percentage .value', container);
	this.fourxx_percentage = $('.stat-4xx_percentage .value', container);
	this.fivexx_percentage = $('.stat-5xx_percentage .value', container);
	this.nginxtime_average = $('.stat-nginxtime_average .value', container);

	// Hook up the show more/less button.
	var showButton = $('.show-all', container);
	var secondary = $('.secondary', container);
	showButton.click(
		function(e)
		{
			if( secondary.is(':visible') )
			{
				showButton.text('Show all');
			}
			else
			{
				showButton.text('Hide');
			}
			secondary.slideToggle();
		}
	);

	var graphButton = $('.show-graph', container);
	this.graphArea = $('.graph', container);
	this.isGraphing = false;
	graphButton.click(
		function(e)
		{
			_self.graphArea.toggle();
			_self.isGraphing = !_self.isGraphing;
			_self.setupGraphArea();
			_self.requestGraph();
		}
	);

	// If the graph area is visible on page load,
	// start graphing now.
	if( this.graphArea.is(':visible') )
	{
		this.setupGraphArea();
		// Don't make the first call to update the graph,
		// because it's likely not ready yet.
		this.isGraphing = true;
	}

	// Connect.
	this.connect();
}

pm.stats.router.prototype = new WebsocketHandler("/router/stats/stream");
pm.stats.router.prototype.constructor = pm.stats.router;

pm.stats.router.prototype.onmessage = function(message)
{
	//console.log(message);
	switch(message.type)
	{
		case 'update':
			this.showUpdate(message.data);
			break;
		case 'history':
			this.showGraph(message.data);
			break;
		case 'ready':
			this.ready = true;
			// Start updating.
			this.requestUpdate();
			if( this.isGraphing )
			{
				this.requestGraph();
			}
			break;
	}
}

pm.stats.router.prototype.setupGraphArea = function()
{
	var options = {
		series: { shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
		yaxis: { min: 0 },
		xaxis: { mode: "time", minTickSize: [30, "second"], }
	};
	this.plot = $.plot(this.graphArea, [], options);
}

pm.stats.router.prototype.requestUpdate = function()
{
	this.send({request: 'update', data: {'name': this.input_name, 'input_id': this.input_id}});
}

pm.stats.router.prototype.requestGraph = function()
{
	var now = new Date();
	// TODO: Allow more configuration, less assumptions.
	this.send(
		{
			request: 'history',
			data: {
				'name': this.input_name,
				'input_id': this.input_id,
				'metric': 'requests',
				'start': (now.getTime() / 1000) - 60
			}
		}
	);
}

pm.stats.router.prototype.displayIncludingLast = function(key, values, container)
{
	var value = '';
	value += number_format(values[key]);

	if( this.lastNumbers )
	{
		var difference = values[key] - this.lastNumbers[key];
		var deltaTime = values['as_at'] - this.lastNumbers['as_at'];

		value += ' - <span class="diff">' + number_format(difference / deltaTime) + '/s</span>';
	}

	container.html(value);
}

pm.stats.router.prototype.showUpdate = function(update)
{
	this.displayIncludingLast('requests', update, this.requests);
	this.displayIncludingLast('bytes', update, this.bytes);
	this.time_average.text(number_format(update.time_average));

	this.displayIncludingLast('1xx', update, this.onexx);
	this.displayIncludingLast('2xx', update, this.twoxx);
	this.displayIncludingLast('3xx', update, this.threexx);
	this.displayIncludingLast('4xx', update, this.fourxx);
	this.displayIncludingLast('5xx', update, this.fivexx);

	this.onexx_percentage.text(toFixed(update['1xx_percentage'], 2) + '%');
	this.twoxx_percentage.text(toFixed(update['2xx_percentage'], 2) + '%');
	this.threexx_percentage.text(toFixed(update['3xx_percentage'], 2) + '%');
	this.fourxx_percentage.text(toFixed(update['4xx_percentage'], 2) + '%');
	this.fivexx_percentage.text(toFixed(update['5xx_percentage'], 2) + '%');
	this.nginxtime_average.text(number_format(update.nginxtime_average));

	// And then in 1s, request it again.
	var _self = this;
	setTimeout(function(){ _self.requestUpdate(); }, 1000);

	this.lastNumbers = update;
}

pm.stats.router.prototype.showGraph = function(graphdata)
{
	//console.log(graphdata.points);
	var graphPoints = graphdata.points;
	if( graphPoints.length == 0 )
	{
		// No data returned. Fake it!
		graphPoints.push([graphdata.start, 0]);
		graphPoints.push([graphdata.end, 0]);
	}
	else
	{
		if( graphPoints[0][0] != graphdata.start )
		{
			// Doesn't start with the start time. Insert
			// a point to make it make sense.
			graphPoints.splice(0, 0, [graphdata.start, 0])
		}
		if( graphPoints[graphPoints.length - 1][0] != graphdata.end )
		{
			// Doesn't end with the end time. Insert a
			// point to make it make sense.
			graphPoints.push([graphdata.end, 0])
		}
	}

	// Now convert all the times to unix timestamp milliseconds.
	for( var i = 0; i < graphPoints.length; i++ )
	{
		graphPoints[i][0] *= 1000;
	}

	//console.log(graphPoints);

	this.plot.setData([graphPoints]);
	this.plot.setupGrid();
	this.plot.draw();

	// And then in 1s, request it again.
	if( this.isGraphing )
	{
		var _self = this;
		setTimeout(function(){ _self.requestGraph(); }, 1000);
	}
}

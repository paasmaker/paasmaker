
if (!window.pm) { var pm = {}; }	// TODO: module handling
pm.stats = {};

pm.stats.routergraph = (function(){
	var module = {};

	module.graph = function(streamSocket, container, statCategory, statInputId) {
		var graph = {};
		var plot;
		var timeout;
		var graphOptions = {
			series: { shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
			yaxis: { min: 0 },
			xaxis: { mode: "time", minTickSize: [30, "second"], }
		};

		// Resolve the container.
		container = $(container);

		// Subscribe to the router history events.
		streamSocket.on(
			'router.stats.history',
			function(serverStatCategory, serverInputId, start, end, history) {
				if(serverStatCategory == statCategory && serverInputId == statInputId) {
					graph.showGraph(start, end, history);

					timeout = setTimeout(function() { graph.requestUpdate() }, 1000);
				}
			}
		);

		// Set up the Flot object.
		plot = $.plot(container, [], graphOptions);

		graph.showGraph = function(start, end, graphPoints)
		{
			if( graphPoints.length == 0 ) {
				// No data returned. Fake it!
				graphPoints.push([start, 0]);
				graphPoints.push([end, 0]);
			}
			else
			{
				if( graphPoints[0][0] != start ) {
					// Doesn't start with the start time. Insert
					// a point to make it make sense.
					graphPoints.splice(0, 0, [start, 0])
				}
				if( graphPoints[graphPoints.length - 1][0] != end ) {
					// Doesn't end with the end time. Insert a
					// point to make it make sense.
					graphPoints.push([end, 0])
				}
			}

			// Now convert all the times to unix timestamp milliseconds.
			for( var i = 0; i < graphPoints.length; i++ ) {
				graphPoints[i][0] *= 1000;
			}

			plot.setData([graphPoints]);
			plot.setupGrid();
			plot.draw();
		}

		graph.requestUpdate = function() {
			// Request an update from the server.
			var now = new Date();
			streamSocket.emit(
				'router.stats.history',
				statCategory,
				statInputId,
				'requests',
				(now.getTime() / 1000) - 60 // Start - 60 seconds ago to now.
			);
		};

		graph.stopUpdating = function() {
			clearTimeout(timeout);
		};

		// Request the first update.
		graph.requestUpdate();

		return graph;
	}

	return module;
}());

pm.stats.routerstats = (function(){
	var module = {};

	module.stats = function(streamSocket, container, statCategory, statInputId, title) {
		var stats = {};

		// Resolve the container.
		container = $(container);
		container.empty();

		// A template for each stats section.
		var statsSectionTemplateRaw = '{{#each statset}}' +
				'<div class="stats-row clearfix">' +
					'<span class="title">{{title}}:</span>' +
					'<span class="value">{{value}}' +
						'{{#if diff}} | <span class="diff">{{diff}}/s</span>{{/if}}' +
					'</span>' +
				'</div>' +
			'{{/each}}';

		var statsSectionTemplate = Handlebars.compile(statsSectionTemplateRaw);

		// Create top level containers.
		if (title) {
			var titleContainer = $('<div class="complete-title"></div>');
			titleContainer.text(title);
			container.append(titleContainer);
		}
		var primaryStats = $('<div class="primary">Loading...</div>');
		var secondaryStats = $('<div class="secondary"></div>');
		var graphArea = $('<div class="graph"></div>');
		var buttonBox = $('<div class="btn-group"></div>');

		container.append(primaryStats);
		container.append(secondaryStats);
		container.append(graphArea);
		container.append(buttonBox);

		var showAllButton = $('<a href="#" class="show-all btn btn-mini">Show all</a>');
		var graphButton = $('<a href="#" class="show-graph btn btn-mini">Show Graph</a>');

		buttonBox.append(showAllButton);
		buttonBox.append(graphButton);

		var graphWidget;

		stats.showGraph = function() {
			graphArea.show();
			graphWidget = pm.stats.routergraph.graph(streamSocket, graphArea, statCategory, statInputId);
			graphButton.text('Hide Graph');
		}

		stats.hideGraph = function() {
			// Stop updating.
			if(graphWidget) {
				graphWidget.stopUpdating();
			}
			graphArea.hide();
			graphButton.text('Show Graph');
		}

		graphButton.click(function(e) {
			if( graphArea.is(':visible') ) {
				stats.hideGraph();
			} else {
				stats.showGraph();
			}

			e.preventDefault();
		});

		// On startup, if the graph area is already visible, show the
		// graph.
		if( graphArea.is(':visible') ) {
			stats.showGraph();
		}

		showAllButton.click(function(e) {
			if( secondaryStats.is(':visible') ) {
				showAllButton.text('Show all');
			} else {
				showAllButton.text('Hide');
			}

			secondaryStats.slideToggle();

			e.preventDefault();
		});

		// Listen to the router stats update event.
		streamSocket.on(
			'router.stats.update',
			function(serverCategoryName, serverCategoryId, serverStats) {
				if( serverCategoryName == statCategory && serverCategoryId == statInputId ) {
					stats.showUpdate(serverStats);

					// And in 1s, get more stats.
					setTimeout(function(){ stats.requestUpdate(); }, 1000);
				}
			}
		);

		streamSocket.on(
			'router.stats.error',
			function(error, serverStatCategory, serverInputId)
			{
				if(serverStatCategory == statCategory && serverInputId == statInputId) {
					// No stats available.
					primaryStats.text("No stats available.");

					timeout = setTimeout(function() { graph.requestUpdate() }, 1000);
				}
			}
		);

		stats.requestUpdate = function() {
			streamSocket.emit('router.stats.update', statCategory, statInputId);
		}

		// To store the last set of numbers, for calculating deltas.
		var lastNumbers;

		var calculateDifference = function(key, values) {
			if( lastNumbers ) {
				var difference = values[key] - lastNumbers[key];
				var deltaTime = values['as_at'] - lastNumbers['as_at'];

				return ' ' + pm.util.number_format(difference / deltaTime);
			} else {
				return '';
			}
		}

		stats.showUpdate = function(update) {
			// Objects to feed into the template for generating the HTML
			// of the stats.
			primaryStatsSet = {
				statset: [
					{
						title: 'Requests',
						value: pm.util.number_format(update.requests),
						diff: calculateDifference('requests', update)
					},
					{
						title: 'Bytes',
						value: pm.util.number_format(update.bytes),
						diff: calculateDifference('bytes', update)
					},
					{
						title: 'Average Time',
						value: pm.util.number_format(update.time_average),
						diff: ''
					}
				]
			};
			secondaryStatsSet = {
				statset: [
					{
						title: '1xx Requests',
						value: update['1xx'],
						diff: ''
					},
					{
						title: '2xx Requests',
						value: update['2xx'],
						diff: ''
					},
					{
						title: '3xx Requests',
						value: update['3xx'],
						diff: ''
					},
					{
						title: '4xx Requests',
						value: update['4xx'],
						diff: ''
					},
					{
						title: '5xx Requests',
						value: update['5xx'],
						diff: ''
					},
					{
						title: 'NGINX time Average',
						value: pm.util.number_format(update.nginxtime_average),
						diff: ''
					}
				]
			}

			primaryStats.html(statsSectionTemplate(primaryStatsSet));
			secondaryStats.html(statsSectionTemplate(secondaryStatsSet));

			lastNumbers = update;
		}

		// Request the first update.
		stats.requestUpdate();

		return stats;
	}

	return module;
}());
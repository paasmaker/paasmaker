
if (!window.pm) { var pm = {}; }	// TODO: module handling
pm.stats = {};

pm.stats.routergraph = (function(){
	var module = {};

	// graph tick generator for the y-axis of byte graphs: ensure the
	// ticks are only round numbers of bytes/kilobytes/megabytes etc.
	var byteTicks = function(axis) {
		var ticks = [];
		var order_of_magnitude = 1;
		var multiplier_index = 0;
		var multipliers = [1, 2.5, 10, 25, 100, 250]
		var number_of_ticks = 1;	// not counting the tick at zero
		var labels = ['', 'kb', 'Mb', 'Gb', 'Tb'];

		while (axis.max > Math.pow(1024, order_of_magnitude) * multipliers[multiplier_index] * number_of_ticks) {
			number_of_ticks ++;
			if (number_of_ticks > 3) {
				number_of_ticks = 1;
				multiplier_index ++;
			}
			if (multiplier_index >= multipliers.length) {
				number_of_ticks = 1;
				multiplier_index = 0;
				order_of_magnitude ++;
			}
		}

		for (var i = 0, value = 0; value < axis.max; i ++) {
			value = i * Math.pow(1024, order_of_magnitude) * multipliers[multiplier_index];
			ticks.push([
			    value,
			    (value / Math.pow(1024, order_of_magnitude)) + labels[order_of_magnitude]
			]);
		}
		return ticks;
	};

	module.types = {
		'requests': {
			socket_request: 'requests',
			flot_options: {
				series: { color: '#edc240', shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
				yaxis: { min: 0 },
				xaxis: { mode: "time", minTickSize: [30, "second"], }
			}
		},
		'bytes': {
			socket_request: 'bytes',
			flot_options: {
				series: { color: '#cb4b4b', shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
				yaxis: { min: 0, ticks: byteTicks },
				xaxis: { mode: "time", minTickSize: [30, "second"], }
			}
		},
		'time': {
			socket_request: 'time',
			flot_options: {
				series: { color: '#afd8f8', shadowSize: 1, lines: { show: true } },
				yaxis: { min: 0 },
				xaxis: { mode: "time", minTickSize: [30, "second"], }
			}
		},
		'requests_by_code': {
			socket_request: ['1xx', '2xx', '3xx', '4xx', '5xx'],
			legend: {
				'1xx': '1xx Informational',
				'2xx': '2xx Successful',
				'3xx': '3xx Redirection',
				'4xx': '4xx Client Error',
				'5xx': '5xx Server Error'
			},
			colours: {
				'1xx': '#3333e0',
				'2xx': '#66e000',
				'3xx': '#dada00',
				'4xx': '#ff9966',
				'5xx': '#a90000'
			},
			flot_options: {
				yaxis: { min: 0 },
				xaxis: { mode: "time", minTickSize: [30, "second"], }
			}
		}
	};

	module.graph = function(container, metric_type, statCategory, statInputId) {
		var graph = {};
		var plot;
		var timeout;
		var graphOptions = module.types[metric_type];

		// Resolve the container.
		container = $(container);

		// Subscribe to the router history events.
		pm.data.subscribe(
			'router.stats.history',
			function(serverStatCategory, serverInputId, start, end, history) {
				if(serverStatCategory == statCategory && serverInputId == statInputId) {
					graph.showGraph(start, end, history);

					timeout = setTimeout(function() { graph.requestUpdate() }, 1000);
				}
			}
		);

		// Set up the Flot object.
		plot = $.plot(container, [], module.types[metric_type].flot_options);

		graph.processData = function(start, end, graphPoints) {
			// If we requested one metric, the structure of graphPoints will already be correct;
			// if we requested several, reformat to suit Flot (adding labels / colours).
			if (typeof module.types[metric_type].socket_request === 'string') {
				return [ graph.processTimeSeries(start, end, graphPoints) ];
			} else {
				var flot_friendly_data = [];

				for (var metric in graphPoints) {
					var series = {};
					series.data = graph.processTimeSeries(start, end, graphPoints[metric]);

					if (module.types[metric_type].legend) {
						series.label = module.types[metric_type].legend[metric];
					}
					if (module.types[metric_type].colours) {
						series.color = module.types[metric_type].colours[metric];
					}

					flot_friendly_data.push(series);
				}

				return flot_friendly_data;
			}
		}

		graph.processTimeSeries = function(start, end, graphPoints) {
			// The python code doesn't return zero values, so walk over graphPoints
			// and insert zeroes for any timestamps that are missing. Also, convert
			// unix timestamps in seconds to milliseconds, to suit Flot.
			var time = Math.floor(start);
			var points_index = 0;
			var processed_points = [];

			while (time < Math.floor(end) + 1) {
				var point = graphPoints[points_index] || [null, 0];
				if (!point[0] || point[0] > time) {
					processed_points.push([ time * 1000, 0 ]);
				} else {
					processed_points.push([ point[0] * 1000, point[1] ]);
					points_index ++;
				}
				time ++;
			}

			if (graphPoints[points_index]) {
				// move the last element of graphPoints if we missed it; TODO: test if this is needed
				console.log(graphPoints.length, points_index);
				processed_points.push([ graphPoints[points_index][0] * 1000, graphPoints[points_index][1] ]);
			}

			return processed_points;
		}

		graph.showGraph = function(start, end, points) {
			plot.setData(graph.processData(start, end, points));
			plot.setupGrid();
			plot.draw();
		}

		graph.requestUpdate = function() {
			// Request an update from the server.
			var now = new Date();
			pm.data.emit(
				'router.stats.history',
				statCategory,
				statInputId,
				module.types[metric_type].socket_request,
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



pm.stats.workspace = (function(){
	return {
		redraw: function() {
			$('.overview-graph').each(function(i, el) {
				el = $(el);
				pm.stats.routergraph.graph($('.graph-container', el), el.data('metric'), el.data('name'), el.data('inputid'));
			});
		}
	}
}());



pm.stats.routerstats = (function(){
	var module = {};

	module.redraw = function() {
		$('.router-stats').each(function(i, el) {
			el = $(el);
			module.stats(el, el.data('name'), el.data('inputid'), el.data('title'));
		});
	};

	module.stats = function(container, statCategory, statInputId, title) {
		var stats = {};

		// Resolve the container.
		container = $(container);
		container.empty();

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

		container.append(
			$('<div class="values">').append(primaryStats,secondaryStats)
		);
		container.append(graphArea);
		container.append(buttonBox);

		var showAllButton = $('<a href="#" class="show-all btn btn-mini">Show All</a>');
		var graphButton = $('<a href="#" class="show-graph btn btn-mini">Show Graph</a>');

		buttonBox.append(showAllButton);
		buttonBox.append(graphButton);

		var graphWidget;

		stats.showGraph = function() {
			graphArea.show();
			graphWidget = pm.stats.routergraph.graph(graphArea, 'requests', statCategory, statInputId);
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

		// On startup, if the graph area is already visible, show the graph.
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
		pm.data.subscribe(
			'router.stats.update',
			function(serverCategoryName, serverCategoryId, serverStats) {
				if( serverCategoryName == statCategory && serverCategoryId == statInputId ) {
					stats.showUpdate(serverStats);

					// And in 1s, get more stats.
					setTimeout(function(){ stats.requestUpdate(); }, 1000);
				}
			}
		);

		pm.data.subscribe(
			'router.stats.error',
			function(error, serverStatCategory, serverInputId)
			{
				if(serverStatCategory == statCategory && serverInputId == statInputId) {
					// No stats available.
					primaryStats.text("No stats available.");
					buttonBox.hide();

					timeout = setTimeout(function() { stats.requestUpdate() }, 1000);
				}
			}
		);

		stats.requestUpdate = function() {
			pm.data.emit('router.stats.update', statCategory, statInputId);
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
						unit: 'ms',
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

			primaryStats.html(pm.handlebars.router_stats_section(primaryStatsSet));
			secondaryStats.html(pm.handlebars.router_stats_section(secondaryStatsSet));

			buttonBox.show();	// in case no stats were available and we hid it

			lastNumbers = update;
		}

		// Request the first update.
		stats.requestUpdate();

		return stats;
	}

	return module;
}());
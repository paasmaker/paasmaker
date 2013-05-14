define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, context, Bases){

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

	var graphTypes = {
		'requests': {
			socket_request: ['requests'],
			flot_options: {
				series: { color: '#edc240', shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
				yaxis: { min: 0 },
				xaxis: { mode: "time", minTickSize: [30, "second"], }
			}
		},
		'bytes': {
			socket_request: ['bytes'],
			flot_options: {
				series: { color: '#cb4b4b', shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
				yaxis: { min: 0, ticks: byteTicks },
				xaxis: { mode: "time", minTickSize: [15, "second"], }
			}
		},
		'time': {
			socket_request: ['time'],
			flot_options: {
				series: { color: '#afd8f8', shadowSize: 1, lines: { show: true } },
				yaxis: { min: 0 },
				xaxis: { mode: "time", minTickSize: [15, "second"], }
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
				xaxis: { mode: "time", minTickSize: [15, "second"], },
				legend: { position: 'sw', sorted: true }
			}
		}
	};

	var GraphView = Bases.BaseView.extend({
		initialize: function() {
			this.timeout = null;
			this.graphOptions = graphTypes[this.options.graphType];
			this.statCategory = this.options.category;
			this.statInputId = this.options.input_id;

			this.updateBinder = _.bind(this.onData, this);
			this.errorBinder = _.bind(this.onError, this);

			context.streamSocket.on('router.history.update', this.updateBinder);
			context.streamSocket.on('router.history.error', this.errorBinder);

			this.plot = $.plot(this.$el, [], this.graphOptions.flot_options);
			this.plot.setupGrid();

			this.awaitingUpdate = false;

			// Request the first update.
			this.requestUpdate();
		},
		destroy: function() {
			context.streamSocket.removeListener('router.history.update', this.updateBinder);
			context.streamSocket.removeListener('router.history.error', this.errorBinder);
			if (this.timeout) {
				clearTimeout(this.timeout);
			}
		},
		requestUpdate: function() {
			if (!this.awaitingUpdate) {
				var now = new Date();
				context.streamSocket.emit(
					'router.history.update',
					this.statCategory,
					this.statInputId,
					this.graphOptions.socket_request,
					(now.getTime() / 1000) - 60
				);
				this.awaitingUpdate = true;
			}
		},
		onData: function(serverStatCategory, serverInputId, start, end, data) {
			if (serverStatCategory == this.statCategory && serverInputId == this.statInputId) {
				this.awaitingUpdate = false;
				var processedData = {};
				$('.graph-error', this.$el.parent()).remove();
				for (var metric in data) {
					if (graphTypes[this.options.graphType].socket_request.indexOf(metric) === -1) {
						// we did not request this metric (but might get it because the subscribe call
						// responds to all router.stats websocket calls, not just the ones we started)
						return false;
					}

					for (var metric in data) {
						processedData[metric] = this.processTimeSeries(start, end, data[metric]);
					}
				}

				this.showGraph(processedData);
				this.timeout = setTimeout(_.bind(this.requestUpdate, this), 1000);
			}
		},
		onError: function(message, serverStatCategory, serverInputId) {
			if (serverStatCategory == this.statCategory && serverInputId == this.statInputId) {
				this.awaitingUpdate = false;
				var errorBox = $('.graph-error', this.$el.parent());
				if (errorBox.length == 0) {
					errorBox = $('<div class="graph-error"></div>');
					container.parent().append(errorBox);
				}
				errorBox.text("Graph error: " + message);

				// Try again in 5 seconds.
				this.timeout = setTimeout(_.bind(this.requestUpdate, this), 5000);
			}
		},
		processTimeSeries: function(start, end, graphPoints) {
			// The python code doesn't return zero values, so walk over graphPoints
			// and insert zeroes for any timestamps that are missing. Also, convert
			// unix timestamps in seconds to milliseconds, to suit Flot.
			var time = Math.floor(start);
			var pointsIndex = 0;
			var processedPoints = [];

			while (time < Math.floor(end) + 1) {
				var point = graphPoints[pointsIndex] || [null, 0];
				if (!point[0] || point[0] > time) {
					processedPoints.push([ time * 1000, 0 ]);
				} else {
					processedPoints.push([ point[0] * 1000, point[1] ]);
					pointsIndex ++;
				}
				time ++;
			}

			if (graphPoints[pointsIndex]) {
				// move the last element of graphPoints if we missed it; TODO: test if this is needed
				processedPoints.push([ graphPoints[pointsIndex][0] * 1000, graphPoints[pointsIndex][1] ]);
			}

			return processedPoints;
		},
		formatDatasetForFlot: function(dataset) {
			var flotFriendlyData = [];

			for (var metric in dataset) {
				var series = {};
				series.data = dataset[metric];

				if (this.graphOptions.legend) {
					series.label = this.graphOptions.legend[metric];
				}
				if (this.graphOptions.colours) {
					series.color = this.graphOptions.colours[metric];
				}

				flotFriendlyData.push(series);
			}

			return flotFriendlyData;
		},
		showGraph: function(dataset) {
			this.plot.setData(this.formatDatasetForFlot(dataset));
			this.plot.setupGrid();
			this.plot.draw();
		}
	});

	return GraphView;
});
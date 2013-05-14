define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/widget/routerstats.html'
], function($, _, Backbone, context, Bases, util, StatsTemplate){

	var StatsView = Bases.BaseView.extend({
		initialize: function() {
			this.statCategory = this.options.category;
			this.statInputId = this.options.input_id;

			this.updateBinder = _.bind(this.onData, this);
			this.errorBinder = _.bind(this.onError, this);

			context.streamSocket.on('router.stats.update', this.updateBinder);
			context.streamSocket.on('router.stats.error', this.errorBinder);

			this.errorMessage = null;
			this.data = null;
			this.awaitingUpdate = false;

			// Request the first update.
			this.requestUpdate();
		},
		destroy: function() {
			context.streamSocket.removeListener('router.stats.update', this.updateBinder);
			context.streamSocket.removeListener('router.stats.error', this.errorBinder);
			if (this.timeout) {
				clearTimeout(this.timeout);
			}
		},
		requestUpdate: function() {
			if (!this.awaitingUpdate) {
				context.streamSocket.emit(
					'router.stats.update',
					this.options.category,
					this.options.input_id
				);
				this.awaitingUpdate = true;
			}
		},
		onData: function(serverStatCategory, serverInputId, data) {
			if (serverStatCategory == this.options.category && serverInputId == this.options.input_id) {
				// Post process the data a little bit.
				this.awaitingUpdate = false;
				var primary = [
					{
						title: 'Requests',
						value: util.number_format(data.requests),
						diff: this.calculateDifference('requests', data)
					},
					{
						title: 'Bytes',
						value: util.number_format(data.bytes),
						diff: this.calculateDifference('bytes', data)
					},
					{
						title: 'Average Time',
						value: util.number_format(data.time_average),
						unit: 'ms',
						diff: ''
					}
				];
				var secondary = [
					{
						title: '1xx Requests',
						value: data['1xx'],
						diff: ''
					},
					{
						title: '2xx Requests',
						value: data['2xx'],
						diff: ''
					},
					{
						title: '3xx Requests',
						value: data['3xx'],
						diff: ''
					},
					{
						title: '4xx Requests',
						value: data['4xx'],
						diff: ''
					},
					{
						title: '5xx Requests',
						value: data['5xx'],
						diff: ''
					},
					{
						title: 'NGINX time Average',
						value: util.number_format(data.nginxtime_average),
						diff: ''
					}
				];

				this.data = {primary: primary, secondary: secondary};
				this.lastNumbers = data;

				this.render();

				this.timeout = setTimeout(_.bind(this.requestUpdate, this), 1000);
			}
		},
		onError: function(message, serverStatCategory, serverInputId) {
			if (serverStatCategory == this.options.category && serverInputId == this.options.input_id) {
				this.awaitingUpdate = false;
				this.errorMessage = message;
				this.data = null;
				this.render();

				// Try again in 5 seconds.
				this.timeout = setTimeout(_.bind(this.requestUpdate, this), 5000);
			}
		},
		render: function() {
			this.$el.html(StatsTemplate({data: this.data, error: this.errorMessage}));
		},
		calculateDifference: function(key, values) {
			if( this.lastNumbers ) {
				var difference = values[key] - this.lastNumbers[key];
				var deltaTime = values['as_at'] - this.lastNumbers['as_at'];

				return ' ' + util.number_format(difference / deltaTime);
			} else {
				return '';
			}
		}
	});

	return StatsView;
});
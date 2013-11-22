define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases'
], function($, _, Backbone, context, Bases){
	var logLevelMap = [
		['DEBUG', 'label', new RegExp('\\d\\sDEBUG\\s', 'g')],
		['INFO', 'label label-info', new RegExp('\\d\\sINFO\\s', 'g')],
		['WARNING', 'label label-warning', new RegExp('\\d\\sWARNING\\s', 'g')],
		['ERROR', 'label label-important', new RegExp('\\d\\sERROR\\s', 'g')],
		['CRITICAL', 'label label-important', new RegExp('\\d\\sCRITICAL\\s', 'g')]
	];

	var LogView = Bases.BaseView.extend({
		initialize: function() {
			this.linesBinder = _.bind(this.onLines, this);
			this.zeroBinder = _.bind(this.onZeroSize, this);
			this.cantFindBinder = _.bind(this.onCantFind, this);
			this.jobId = this.$el.data('jobid');

			context.streamSocket.on('log.lines', this.linesBinder);
			context.streamSocket.on('log.zerosize', this.zeroBinder);
			context.streamSocket.on('log.cantfind', this.cantFindBinder);

			this.isReading = false;
		},
		isScrolledToBottom: function() {
			var content_height = this.$el.scrollHeight;
			var current_view_bottom = this.$el.scrollTop + this.$el.innerHeight();
			return (content_height == current_view_bottom);
		},
		onLines: function(job_id, lines, position) {
			if (this.jobId != job_id) { return; }

			if (!this.$el.hasClass('data')) {
				this.$el.empty();
			}

			if (this.isScrolledToBottom()) {
				var reset_scroll = true;
			}

			this.$el.data('position', position);
			this.$el.addClass('data');
			this.$el.append(this.formatLogLines(lines));

			if (reset_scroll) {
				// TODO: test this across browsers
				this.$el.scrollTop = this.$el.scrollHeight;
			}
		},
		onZeroSize: function(job_id) {
			if (this.jobId != job_id) { return; }

			this.$el.text('This log is currently empty.');
			this.$el.removeClass('data');
		},
		onCantFind: function(job_id, error_message) {
			if (this.jobId != job_id) { return; }

			this.$el.text(error_message);
			this.$el.removeClass('data');
		},
		start: function() {
			if (!this.isReading) {
				var position = this.$el.data('position');
				if (!position) {
					position = 0;
				}

				context.streamSocket.emit('log.subscribe', this.jobId, position);

				this.isReading = true;
			}
		},
		pause: function() {
			if (this.isReading) {
				context.streamSocket.emit('log.unsubscribe', this.jobId);
				this.isReading = false;
			}
		},
		destroy: function() {
			if (this.isReading) {
				context.streamSocket.emit('log.unsubscribe', this.jobId);
			}
			context.streamSocket.removeListener('log.lines', this.linesBinder);
			context.streamSocket.removeListener('log.zerosize', this.zeroBinder);
			context.streamSocket.removeListener('log.cantfind', this.cantFindBinder);
		},
		formatLogLines: function(lines) {
			var output = lines.join("");
			output = _.escape(output);
			for( var i = 0; i < logLevelMap.length; i++ ) {
				output = output.replace(
					logLevelMap[i][2],
					' <span class="' + logLevelMap[i][1] + '">' + logLevelMap[i][0] + '</span> '
				);
			}
			return output;
		}
	});

	return LogView;
});
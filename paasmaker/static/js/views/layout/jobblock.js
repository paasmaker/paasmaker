define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/layout/jobblock.html',
	'views/layout/logviewer'
], function($, _, Backbone, context, Bases, JobBlockTemplate, LogView){
	var statusClassMap = {
		'FAILED': 'important',
		'ABORTED': 'warning',
		'SUCCESS': 'success',
		'WAITING': 'info',
		'RUNNING': 'primary'
	};

	var statusIconMap = {
		'FAILED': 'icon-remove',
		'ABORTED': 'icon-ban-circle',
		'SUCCESS': 'icon-ok',
		'WAITING': 'icon-time',
		'RUNNING': 'icon-loading',
		'NEW': 'icon-certificate'
	};

	var finishedStates = ['SUCCESS', 'FAILED', 'ABORTED'];

	var JobBlockView = Bases.BaseView.extend({
		initialize: function() {
			this.myJobs = {};
			this.myJobs[this.options.job_id] = true;
			this.logViewers = {};

			this.gotJobTreeBinder = _.bind(this.gotJobTree, this);
			context.streamSocket.on('job.tree', this.gotJobTreeBinder);

			this.gotJobStatusBinder = _.bind(this.gotJobStatus, this);
			context.streamSocket.on('job.status', this.gotJobStatusBinder);

			// Fetch the initial tree for this job.
			context.streamSocket.emit('job.tree', this.options.job_id);
		},
		events: {
			"click a.viewlog": "viewLog"
		},
		render: function() {
			// Render the initial job tree.
			this.$el.html(this.renderRecurse(this.jobTree, true));
		},
		renderRecurse: function(root, isRoot) {
			// Render this level. Direct to a series of DOM
			// elements.
			var isFinished = _.indexOf(finishedStates, root.state) != -1;
			var thisLevel = $(JobBlockTemplate({
				job: root,
				statusClassMap: statusClassMap,
				statusIconMap: statusIconMap,
				finishedStates: finishedStates,
				isFinished: isFinished,
				isRoot: isRoot
			}));

			// Record this as one of "my" jobs.
			this.myJobs[root.job_id] = true;

			// TODO: This is a bit fragile, but $('.children', thisLevel)
			// didn't work because it's not attached to the DOM yet?
			var thisChildContainer = $(thisLevel[4]);

			// Sort the children based on their time.
			root.children.sort(function(a, b) {
				return a.time - b.time;
			});

			// Then render the children and add them to this level.
			for (var i = 0; i < root.children.length; i++ ) {
				var container = $('<div class="job clearfix"></div>');
				var thisChild = this.renderRecurse(root.children[i]);
				container.html(thisChild);
				thisChildContainer.append(container);
			}

			return thisLevel;
		},
		gotJobTree: function(job_id, tree) {
			// Is it for us?
			if (!this.myJobs[job_id]) { return; }

			this.jobTree = tree;

			this.render();
		},
		gotJobStatus: function(job_id, status) {
			// Is it for us?
			if (!this.myJobs[job_id]) { return; }

			var titleBlock = $('.title-' + job_id, this.$el);
			if (titleBlock.length) {
				var stateLabel = $('span.icon', titleBlock);
				var stateIcon = $('i', titleBlock);

				stateLabel.attr('class', 'icon label label-' + statusClassMap[status.state]);
				stateIcon.attr('class', 'icon-white ' + statusIconMap[status.state]);
			}

			var finished = _.indexOf(finishedStates, job.state) != -1;

			// If the root job finishes, remove the abort button.
			if (job_id == this.options.job_id) {
				if (finished ) {
					// Remove the abort button.
					$('.abort', this.$el).remove();
				}
			}

			// If the job finished, and it wasn't successful, populate the summary box.
			if (finished && job.state != "SUCCESS") {
				var summaryBox = $('.particulars-' + job_id + ' .summary', this.$el);
				summaryBox.text(job.summary);
				summaryBox.attr('class', 'summary summary-' + job.state);
			}
		},
		viewLog: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var jobId = el.data('jobid');

			var logContainer = this.$('.particulars-' + jobId + ' .log');
			if (logContainer.is(":visible")) {
				this.$('.particulars-' + jobId + ' .log').slideUp();
				if (this.logViewers[jobId]) {
					this.logViewers[jobId].pause();
				}
			} else {
				this.$('.particulars-' + jobId + ' .log').slideDown();

				if (!this.logViewers[jobId]) {
					this.logViewers[jobId] = new LogView({el: $('pre', logContainer)});
				}
				this.logViewers[jobId].start();
			}
		},
		destroy: function() {
			context.streamSocket.removeListener('job.tree', this.gotJobTreeBinder);
			context.streamSocket.removeListener('job.status', this.gotJobStatusBinder);

			// Destroy any log viewers.
			_.each(this.logViewers, function(value, key, list) {
				value.destroy();
			});
		}
	});

	return JobBlockView;
});
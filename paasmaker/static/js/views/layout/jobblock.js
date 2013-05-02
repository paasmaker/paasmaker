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

			// Fetch the initial tree for this job.
			context.streamSocket.emit('job.tree', this.options.job_id);
		},
		events: {
			"click a.viewlog": "viewLog"
		},
		render: function() {
			// Render the initial job tree.
			this.$el.html(this.renderRecurse(this.jobTree));
		},
		renderRecurse: function(root) {
			// Render this level. Direct to a series of DOM
			// elements.
			var thisLevel = $(JobBlockTemplate({
				job: root,
				statusClassMap: statusClassMap,
				statusIconMap: statusIconMap,
				finishedStates: finishedStates,
				isFinished: _.indexOf(finishedStates, root.state) != -1
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

			// Destroy any log viewers.
			_.each(this.logViewers, function(value, key, list) {
				value.destroy();
			});
		}
	});

	return JobBlockView;
});
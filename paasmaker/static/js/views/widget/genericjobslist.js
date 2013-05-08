define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/widget/joblist.html',
	'views/widget/jobblock'
], function($, _, Backbone, context, Bases, JobListTemplate, JobBlockView){
	var GenericJobsListView = Bases.BaseView.extend({
		initialize: function() {
			this.$el.html(
				Bases.errorLoadingHtml + '<h1>Loading...</h1>'
			);
			this.startLoadingFull();
			this.myJobs = {};
			this.views = [];

			// Request the job list from the server.
			$.ajax({
				url: this.options.url,
				dataType: 'json',
				success: _.bind(this.gotJobList, this),
				error: _.bind(this.loadingError, this)
			});
		},
		gotJobList: function(data) {
			this.doneLoading();
			this.jobs = data.data.jobs;
			this.job_detail = data.data.job_detail;
			this.render();
		},
		render: function() {
			this.$el.html(JobListTemplate({
				jobs: this.jobs,
				job_detail: this.job_detail,
				title: this.options.title,
				context: context,
				_: _
			}));

			// For all jobs, create a view to render them.
			var _self = this;
			this.$('.job').each(function(index, element) {
				var el = $(element);
				var job_id = el.data('jobid');

				var view = new JobBlockView({
					job_id: job_id,
					el: el
				});

				_self.views.push(view);
			});
		},
		loadingError: function(model, xhr, options) {
			this.$('h1').remove();
			// Call the parent loadingError().
			Bases.BaseView.prototype.loadingError.apply(this, [model, xhr, options]);
		},
		destroy: function() {
			for (var i = 0; i < this.views.length; i++) {
				this.views[i].destroy();
			}
		}
	});

	return GenericJobsListView;
});
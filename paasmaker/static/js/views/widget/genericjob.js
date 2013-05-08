define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/widget/jobsingle.html',
	'views/widget/jobblock'
], function($, _, Backbone, context, Bases, JobSingleTemplate, JobBlockView){
	var GenericJobView = Bases.BaseView.extend({
		initialize: function() {
			this.render();
			this.block = null;
		},
		render: function() {
			// Create the element for our job.
			this.$el.html(JobSingleTemplate({
				title: this.options.title,
				job_id: this.options.job_id
			}));

			var blockContainer = this.$('.job-' + this.options.job_id);
			this.block = new JobBlockView({
				job_id: this.options.job_id,
				el: blockContainer
			});
		},
		destroy: function() {
			if (this.block) {
				this.block.destroy();
			}
		}
	});

	return GenericJobView;
});
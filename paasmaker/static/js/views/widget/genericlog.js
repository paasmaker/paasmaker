define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/widget/logsingle.html',
	'views/widget/logviewer'
], function($, _, Backbone, context, Bases, LogSingleTemplate, LogViewer){
	var GenericLogView = Bases.BaseView.extend({
		initialize: function() {
			this.render();
			this.block = null;
		},
		render: function() {
			// Create the element for our job.
			this.$el.html(LogSingleTemplate({
				title: this.options.title,
				job_id: this.options.job_id
			}));

			this.block = new LogViewer({
				el: this.$('pre')
			});

			this.block.start();
		},
		destroy: function() {
			if (this.block) {
				this.block.destroy();
			}
		}
	});

	return GenericLogView;
});
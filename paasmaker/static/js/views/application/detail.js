define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/application/detail.html'
], function($, _, Backbone, context, Bases, ApplicationDetailTemplate){
	var ApplicationDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context
			}));
		},
		destroy: function() {
			this.model.off('request', this.startLoadingFull, this);
			this.model.off('change', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context
			}));

			return this;
		},
		events: {
			"click a.virtual": "navigateAway",
			"click a.delete": "deleteConfirm",
			"click button.realDelete": "realDelete",
			"click button.noDelete": "deleteCancel"
		},
		deleteConfirm: function(e) {
			e.preventDefault();
			this.$('.deleteConfirm').slideDown();
		},
		deleteCancel: function(e) {
			e.preventDefault();
			this.$('.deleteConfirm').slideUp();
		},
		realDelete: function(e) {
			e.preventDefault();

			var _self = this;

			this.startLoadingFull();
			var endpoint = '/application/' + this.model.id + '/delete?format=json';
			$.ajax({
				url: endpoint,
				type: 'POST',
				dataType: 'json',
				success: function(data) {
					_self.doneLoading();

					context.navigate('/application/' + _self.model.id + '/delete/' + data.data.job_id);
				},
				error: _.bind(this.loadingError, this)
			});
		}
	});

	return ApplicationDetailView;
});
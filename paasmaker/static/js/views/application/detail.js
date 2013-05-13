define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'views/widget/routerstats',
	'tpl!templates/application/detail.html'
], function($, _, Backbone, context, Bases, RouterStatsView, ApplicationDetailTemplate){
	var ApplicationDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);
			this.model.versions.on('request', this.startLoadingInline, this);
			this.model.versions.on('change', this.render, this);
			this.model.versions.on('sync', this.render, this);

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context
			}));

			this.routerStats = null;
		},
		destroy: function() {
			this.model.off('request', this.startLoadingFull, this);
			this.model.off('change', this.render, this);
			this.model.versions.off('request', this.startLoadingInline, this);
			this.model.versions.off('change', this.render, this);
			this.model.versions.off('sync', this.render, this);

			if (this.routerStats) {
				console.log("Destroy - exit");
				this.routerStats.destroy();
			}

			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context
			}));

			if (this.routerStats) {
				console.log("Destroy");
				this.routerStats.destroy();
			}

			console.log("Create");
			this.routerStats = new RouterStatsView({
				el: this.$('.router-stats'),
				category: 'application',
				input_id: this.model.id
			});

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
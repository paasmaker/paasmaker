define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'views/widget/routerstats',
	'tpl!templates/application/detail.html',
	'models/version'
], function($, _, Backbone, context, Bases, RouterStatsView, ApplicationDetailTemplate, VersionModel){
	var ApplicationDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);
			this.model.versions.on('request', this.startLoadingInline, this);
			this.model.versions.on('change', this.render, this);
			this.model.versions.on('sync', this.render, this);

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context,
				VersionModel: VersionModel
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
				this.routerStats.destroy();
			}

			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationDetailTemplate({
				application: this.model,
				context: context,
				VersionModel: VersionModel
			}));

			if (this.routerStats) {
				this.routerStats.destroy();
			}

			this.routerStats = new RouterStatsView({
				el: this.$('.router-stats'),
				category: 'application',
				input_id: this.model.id
			});

			return this;
		},
		events: {
			"click a.virtual": "navigateAway",
			"click a.deleteApplication": "deleteConfirm",
			"click button.realDelete": "realDelete",
			"click button.noDelete": "deleteCancel",

			// TODO: These are duplicated from the version view.
			"click a.start": "startVersion",
			"click a.register": "registerVersion",
			"click a.stop": "stopVersion",
			"click a.deregister": "deregisterVersion",
			"click a.makecurrent": "makeCurrentVersion",
			"click a.deleteVersion": "deleteVersion"
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
		},

		// TODO: This is duplicated from the version view.
		makeJobRequest: function(endpoint, version_id) {
			var _self = this;

			this.startLoadingFull();
			var finalEndpoint = '/version/' + version_id + '/' + endpoint + '?format=json';
			$.ajax({
				url: finalEndpoint,
				type: 'POST',
				dataType: 'json',
				success: function(data) {
					_self.doneLoading();

					context.navigate('/version/' + version_id + '/' + endpoint + '/' + data.data.job_id);
				},
				error: _.bind(this.loadingError, this)
			});
		},
		startVersion: function(e) {
			e.preventDefault();
			this.makeJobRequest('start', $(e.currentTarget).data('version'));
		},
		registerVersion: function(e) {
			e.preventDefault();
			this.makeJobRequest('register', $(e.currentTarget).data('version'));
		},
		stopVersion: function(e) {
			e.preventDefault();
			this.makeJobRequest('stop', $(e.currentTarget).data('version'));
		},
		deregisterVersion: function(e) {
			e.preventDefault();
			this.makeJobRequest('deregister', $(e.currentTarget).data('version'));
		},
		makeCurrentVersion: function(e) {
			e.preventDefault();
			this.makeJobRequest('setcurrent', $(e.currentTarget).data('version'));
		},
		deleteVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();

			var _self = this;
			$.ajax({
				url: '/version/' + $(e.currentTarget).data('version') + '/delete?format=json',
				type: 'POST',
				dataType: 'json',
				success: function(data) {
					_self.doneLoading();

					// Update the sidebar.
					var workspace = context.workspaces.get(_self.model.attributes.workspace.id);
					workspace.fetch();
					var application = workspace.applications.get(_self.model.attributes.application_id);
					application.fetch();
					application.versions.fetch();

					// And view the parent application.
					context.navigate('/application/' + _self.model.attributes.application_id);
				},
				error: _.bind(this.loadingError, this)
			});
		}
	});

	return ApplicationDetailView;
});
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/version/detail.html'
], function($, _, Backbone, context, Bases, VersionDetailTemplate){
	var VersionDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);

			this.$el.html(VersionDetailTemplate({
				version: this.model,
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

			this.$el.html(VersionDetailTemplate({
				version: this.model,
				context: context
			}));

			return this;
		},
		events: {
			"click a.start": "startVersion",
			"click a.register": "registerVersion",
			"click a.stop": "stopVersion",
			"click a.deregister": "deregisterVersion",
			"click a.makecurrent": "makeCurrentVersion",
			"click a.delete": "deleteVersion"
		},
		makeJobRequest: function(endpoint) {
			var _self = this;

			var finalEndpoint = '/version/' + this.model.id + '/' + endpoint + '?format=json';
			$.ajax({
				url: finalEndpoint,
				type: 'POST',
				dataType: 'json',
				success: function(data) {
					_self.doneLoading();

					context.navigate('/version/' + _self.model.id + '/' + endpoint + '/' + data.data.job_id);
				},
				error: _.bind(this.loadingError, this)
			});
		},
		startVersion: function(e) {
			this.startLoadingFull();
			this.makeJobRequest('start');

			e.preventDefault();
		},
		registerVersion: function(e) {
			this.startLoadingFull();
			this.makeJobRequest('register');

			e.preventDefault();
		},
		stopVersion: function(e) {
			this.startLoadingFull();
			this.makeJobRequest('stop');

			e.preventDefault();
		},
		deregisterVersion: function(e) {
			this.startLoadingFull();
			this.makeJobRequest('deregister');

			e.preventDefault();
		},
		makeCurrentVersion: function(e) {
			this.startLoadingFull();
			this.makeJobRequest('makecurrent');

			e.preventDefault();
		},
		deleteVersion: function(e) {
			this.startLoadingFull();
			// This isn't a job.
			// TODO: Implement.
			//this.makeJobRequest('delete');

			e.preventDefault();
		}
	});

	return VersionDetailView;
});
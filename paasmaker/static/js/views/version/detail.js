define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/version/detail.html',
	'tpl!templates/version/instances.html'
], function($, _, Backbone, context, Bases, util, VersionDetailTemplate, VersionInstancesTemplate){
	var VersionDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('request', this.startLoadingInline, this);
			this.model.on('change', this.render, this);

			this.$el.html(Bases.errorLoadingHtml + '<div class="top"></div><div class="bottom"></div>');

			this.$('.top').html(VersionDetailTemplate({
				version: this.model,
				context: context
			}));

			// Fetch the instances data.
			this.loadInstanceData();
		},
		destroy: function() {
			this.model.off('request', this.startLoadingFull, this);
			this.model.off('change', this.render, this);
			this.undelegateEvents();
		},
		loadInstanceData: function() {
			this.startLoadingInline();
			$.ajax({
				url: '/version/' + this.model.id + '/instances?format=json',
				dataType: 'json',
				success: _.bind(this.gotInstanceData, this),
				error: _.bind(this.loadingError, this)
			});
		},
		gotInstanceData: function(data) {
			this.instances = data.data.instances;
			this.frontend_domain_postfix = data.data.frontend_domain_postfix;
			this.renderInstances();
		},
		render: function() {
			this.doneLoading();

			this.$('.top').html(VersionDetailTemplate({
				version: this.model,
				context: context,
				_: _
			}));

			return this;
		},
		renderInstances: function() {
			this.doneLoading();

			this.$('.bottom').html(VersionInstancesTemplate({
				version: this.model,
				instanceTypes: this.instances,
				context: context,
				frontend_domain_postfix: this.frontend_domain_postfix,
				is_current: this.model.attributes.is_current,
				_: _
			}));

			util.shrinkUuids(this.$el);

			this.delegateEvents();
		},
		events: {
			"click a.virtual": "navigateAway",
			"click a.start": "startVersion",
			"click a.register": "registerVersion",
			"click a.stop": "stopVersion",
			"click a.deregister": "deregisterVersion",
			"click a.makecurrent": "makeCurrentVersion",
			"click a.delete": "deleteVersion",
			"click button.changeQuantity": "changeQuantity"
		},
		makeJobRequest: function(endpoint, data) {
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
			e.preventDefault();
			this.startLoadingFull();
			this.makeJobRequest('start');
		},
		registerVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.makeJobRequest('register');
		},
		stopVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.makeJobRequest('stop');
		},
		deregisterVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.makeJobRequest('deregister');
		},
		makeCurrentVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.makeJobRequest('setcurrent');
		},
		deleteVersion: function(e) {
			e.preventDefault();
			this.startLoadingFull();

			var _self = this;
			$.ajax({
				url: '/version/' + this.model.id + '/delete?format=json',
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
		},
		changeQuantity: function(e) {
			e.preventDefault();

			this.startLoadingFull();

			var form = $(e.currentTarget).parent();
			var instanceTypeId = $('input[name=instance_type_id]', form).val();
			var quantity = parseInt($('input[name=quantity]', form).val(), 10);

			var _self = this;
			$.ajax({
				url: '/instancetype/' + instanceTypeId + '/quantity?format=json',
				type: 'POST',
				dataType: 'json',
				data: JSON.stringify({
					data: {
						quantity: quantity
					}
				}),
				success: function(data) {
					_self.doneLoading();

					context.navigate('/version/' + _self.model.id + '/quantity/' + data.data.job_id);
				},
				error: _.bind(this.loadingError, this)
			});
		}
	});

	return VersionDetailView;
});
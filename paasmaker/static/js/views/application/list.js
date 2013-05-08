define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/application/list.html',
	'views/widget/graph'
], function($, _, Backbone, context, Bases, ApplicationListTemplate, GraphView){
	var ApplicationListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(ApplicationListTemplate({
				workspace: this.options.workspace,
				applications: [],
				context: context,
				healthClasses: this.collection.healthClasses
			}));

			this.views = [];
		},
		destroy: function() {
			_.each(this.views, function(view, index, list) {
				view.destroy();
			});

			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(ApplicationListTemplate({
				workspace: this.options.workspace,
				applications: this.collection.models,
				context: context,
				healthClasses: this.collection.healthClasses
			}));

			this.views.push(new GraphView({
				graphType: 'requests_by_code',
				category: 'workspace',
				input_id: this.options.workspace.id,
				el: this.$('.graph-requests .graph-tile-inner')
			}));
			this.views.push(new GraphView({
				graphType: 'bytes',
				category: 'workspace',
				input_id: this.options.workspace.id,
				el: this.$('.graph-bytes .graph-tile-inner')
			}));

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return ApplicationListView;
});
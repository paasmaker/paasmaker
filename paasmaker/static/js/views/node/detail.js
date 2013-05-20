define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'util',
	'tpl!templates/node/detail.html',
	'views/node/instances'
], function($, _, Backbone, context, Bases, util, NodeDetailTemplate, NodeInstancesView){
	var NodeDetailView = Bases.BaseView.extend({
		initialize: function() {
			if (this.model) {
				this.model.on('change', this.render, this);
				this.render();
			} else {
				this.startLoadingFull();
			}
		},
		destroy: function() {
			if (this.model) {
				this.model.off('change', this.render, this);
			}
			if (this.nodeInstancesView) {
				this.nodeInstancesView.destroy();
			}
			this.undelegateEvents();
		},
		render: function() {
			this.$el.html(NodeDetailTemplate({
				context: context,
				node: this.model
			}));

			util.shrinkUuids(this.$el);

			if (this.model.attributes.stats.disk_total && this.model.attributes.stats.disk_free) {
				$.plot(this.$('.node-disk .chart'), [
					{ label: "Disk used", color: "darkviolet", data: (this.model.attributes.stats.disk_total - this.model.attributes.stats.disk_free) },
					{ label: "Disk free", color: "lightblue", data: this.model.attributes.stats.disk_free }
				], { series: { pie: { show: true } }, legend: { container: this.$('.node-disk .legend') } });
			}
			if (this.model.attributes.stats.mem_total && this.model.attributes.stats.mem_adjusted_free) {
				$.plot(this.$('.node-memory .chart'), [
					{ label: "Memory used", color: "darksalmon", data: (this.model.attributes.stats.mem_total - this.model.attributes.stats.mem_adjusted_free) },
					{ label: "Memory free", color: "lightblue", data: this.model.attributes.stats.mem_adjusted_free }
				], { series: { pie: { show: true } }, legend: { container: this.$('.node-memory .legend') } });
			}

			this.nodeInstancesView = new NodeInstancesView({
				collection: this.model.instances,
				el: this.$('.instances-list')
			});
			this.model.instances.fetch();

			return this;
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return NodeDetailView;
});
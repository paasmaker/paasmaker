define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/node/detail.html'
], function($, _, Backbone, context, Bases, NodeDetailTemplate){
	var NodeDetailView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('change', this.render, this);
			this.render();
		},
		render: function() {
			this.$el.html(NodeDetailTemplate({
				context: context,
				node: this.model
			}));

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
		},
		events: {
			"click a": "navigateAway",
		}
	});

	return NodeDetailView;
});
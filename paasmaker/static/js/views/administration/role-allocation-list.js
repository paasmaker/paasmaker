define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/role-allocation-list.html'
], function($, _, Backbone, context, Bases, RoleAllocationListTemplate){
	var RoleAllocationListView = Bases.BaseView.extend({
		initialize: function() {
			this.collection.on('request', this.startLoadingFull, this);
			this.collection.on('sync', this.render, this);

			this.$el.html(RoleAllocationListTemplate({
				allocations: [],
				context: context
			}));
		},
		destroy: function() {
			this.collection.off('request', this.startLoadingFull, this);
			this.collection.off('sync', this.render, this);
			this.undelegateEvents();
		},
		render: function() {
			this.doneLoading();

			this.$el.html(Bases.errorLoadingHtml + RoleAllocationListTemplate({
				allocations: this.collection.models,
				context: context
			}));

			return this;
		},
		events: {
			"click button.remove": "removeAllocation",
			"click a": "navigateAway",
		},
		removeAllocation: function(e) {
			e.preventDefault();
			var el = $(e.currentTarget);
			var allocationId = el.data('allocation');

			var _self = this;
			$.ajax(
				'/role/allocation/unassign?format=json',
				{
					type: 'POST',
					data: JSON.stringify({
						data: {
							allocation_id: allocationId
						}
					}),
					dataType: 'json',
					success: function() {
						_self.startLoadingFull();
						_self.collection.fetch();
					},
					error: _.bind(this.loadingError, this)
				}
			);
			this.startLoadingInline();
		}
	});

	return RoleAllocationListView;
});
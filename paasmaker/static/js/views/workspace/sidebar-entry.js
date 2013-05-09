define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/workspace/sidebar-entry.html'
], function($, _, Backbone, context, Bases, WorkspaceSidebarEntryTemplate){
	var WorkspaceSidebarEntryView = Bases.BaseView.extend({
		initialize: function() {
			this.model.on('change', this.render, this);
			this.model.applications.on('sync', this.renderApplications, this);
			this.render();

			this.$el.html(WorkspaceSidebarEntryTemplate({
				context: context,
				workspace: this.model
			}));
		},
		render: function() {
			// Just update the existing HTML.
			this.$('.workspace-title').text(this.model.attributes.name);
			if (this.model.attributes.active) {
				this.$el.addClass("active");
			} else {
				this.$el.removeClass("active");
			}
		},
		renderApplications: function() {
			var container = this.$('.applications');
			this.model.applications.each(function(application, index, list) {
			});
		},
		events: {
			"click a.virtual": "navigateAway",
			"click a.expand-applications": "expandApplications"
		},
		expandApplications: function(e) {
			e.preventDefault();

			if (this.$('.applications').is(':visible')) {
				this.$('.applications').slideUp();
				this.$('a.expand-applications i').attr('class', 'icon-chevron-down');
			} else {
				this.$('.applications').slideDown();
				this.$('a.expand-applications i').attr('class', 'icon-chevron-up');
			}
		}
	});

	return WorkspaceSidebarEntryView;
});
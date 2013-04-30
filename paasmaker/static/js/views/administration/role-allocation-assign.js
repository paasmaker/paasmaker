define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/role-allocation-assign.html',
	'models/roleallocation'
], function($, _, Backbone, context, Bases, RoleAllocationAssignTemplate, RoleAllocationModel){
	var RoleAllocationAssignView = Bases.BaseView.extend({
		initialize: function() {
			context.roles.on('sync', this.renderRoles, this);
			context.workspaces.on('sync', this.renderWorkspaces, this);
			context.users.on('sync', this.renderUsers, this);

			this.$el.html(Bases.errorLoadingHtml + RoleAllocationAssignTemplate({
				context: context
			}));

			this.renderRoles(context.roles);
			this.renderWorkspaces(context.workspaces);
			this.renderUsers(context.users);
		},
		destroy: function() {
			context.roles.off('sync', this.renderRoles, this);
			context.workspaces.off('sync', this.renderWorkspaces, this);
			context.users.off('sync', this.renderUsers, this);

			this.undelegateEvents();
		},
		renderRoles: function(collection, response, options) {
			this.renderSelect(collection, this.$('#role_id'));
		},
		renderWorkspaces: function(collection, response, options) {
			var select = this.$('#workspace_id');
			this.renderSelect(collection, select);
			select.prepend($('<option value="">-- Global</option>'));
		},
		renderUsers: function(collection, response, options) {
			this.renderSelect(collection, this.$('#user_id'));
		},
		renderSelect: function(collection, select) {
			select.empty();
			collection.each(function(element, index, list) {
				var op = $('<option></option>');
				op.attr('value', element.attributes.id);
				op.text(element.attributes.name);
				select.append(op);
			});
		},
		saveModel: function(e) {
			e.preventDefault();
			this.startLoadingFull();

			var model = new RoleAllocationModel();
			model.save({
				user_id: this.$('#user_id').val(),
				role_id: this.$('#role_id').val(),
				workspace_id: this.$('#workspace_id').val()
			}, {
				success: _.bind(this.saveOk, this),
				error: _.bind(this.loadingError, this)
			});
		},
		saveOk: function() {
			context.navigate("/role/allocation/list");
		},
		events: {
			"click button": "saveModel"
		}
	});

	return RoleAllocationAssignView;
});
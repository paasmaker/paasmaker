define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/role-edit.html',
	'models/role'
], function($, _, Backbone, context, Bases, RoleEditTemplate, RoleModel){
	var RoleEditView = Bases.BaseView.extend({
		initialize: function() {
			if (!this.model) {
				this.newRole = true;
				this.model = new RoleModel();
			} else {
				this.newRole = false;
			}

			this.render();
		},
		render: function() {
			this.$el.html(Bases.errorLoadingHtml + RoleEditTemplate({
				role: this.model,
				context: context,
				newRole: this.newRole,
				// Read from the global available permissions.
				availablePermissions: available_permissions,
				_: _
			}));

			return this;
		},
		saveModel: function(e) {
			e.preventDefault();
			this.startLoadingFull();

			var permissions = [];
			for (var i = 0; i < available_permissions.length; i++) {
				if (this.$('input[name=' + available_permissions[i] + ']').is(':checked')) {
					permissions.push(available_permissions[i]);
				}
			}

			this.model.save({
				name: this.$('#name').val(),
				permissions: permissions
			}, {
				success: _.bind(this.saveOk, this),
				error: _.bind(this.loadingError, this)
			});
		},
		saveOk: function() {
			context.navigate("/role/list");
		},
		events: {
			"click button": "saveModel"
		}
	});

	return RoleEditView;
});
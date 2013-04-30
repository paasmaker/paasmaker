define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/administration/user-edit.html',
	'models/user'
], function($, _, Backbone, context, Bases, UserEditTemplate, UserModel){
	var UserEditView = Bases.BaseView.extend({
		initialize: function() {
			if (!this.model) {
				this.newUser = true;
				this.model = new UserModel();
			} else {
				this.newUser = false;
			}

			this.render();
		},
		render: function() {
			this.$el.html(Bases.errorLoadingHtml + UserEditTemplate({
				user: this.model,
				context: context,
				newUser: this.newUser
			}));

			return this;
		},
		saveModel: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.model.save({
				name: this.$('#name').val(),
				login: this.$('#login').val(),
				email: this.$('#email').val(),
				enabled: this.$('#enabled').is(':checked'),
				password: this.$('#password').val()
			}, {
				success: _.bind(this.saveOk, this),
				error: _.bind(this.loadingError, this)
			});
		},
		saveOk: function(arg, arg2, arg3) {
			context.navigate("/user/list");
		},
		events: {
			"click button": "saveModel",
		}
	});

	return UserEditView;
});
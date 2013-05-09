define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'bases',
	'tpl!templates/workspace/edit.html',
	'models/workspace'
], function($, _, Backbone, context, Bases, WorkspaceEditTemplate, WorkspaceModel){
	var WorkspaceEditView = Bases.BaseView.extend({
		initialize: function() {
			if (!this.model) {
				this.newWorkspace = true;
				this.model = new WorkspaceModel();
			} else {
				this.newWorkspace = false;
			}

			this.render();
		},
		render: function() {
			this.$el.html(Bases.errorLoadingHtml + WorkspaceEditTemplate({
				workspace: this.model,
				context: context,
				newWorkspace: this.newWorkspace
			}));

			// TODO: Properly load this CSS file another way.
			$('head').append('<link rel="stylesheet" href="/static/css/tag_editor.css">');

			this.$('.workspace-tag-editor').jsonEditor(
				{
					Tags: this.model.attributes.tags
				},
				{
					newSingleKey: "New Tag",
					newGroupKey: "Tag Group",
					change: function(updated) {
						this.$('#tags').val(JSON.stringify(updated.Tags));
						this.$('#tags').data('tags', updated.Tags);
					},
					drawproperty: function(opt, json, root, path, key) {
						children = {};
						if (key == 'Tags' && Object.prototype.toString.call(json[key]) == '[object Object]') {
							children.item = $('<div>', { 'class': 'item', 'data-path': path });
							children.item.addClass('expanded group-top-level');
							children.property = $(opt.headerElement || '<span class="property group-header">' + key + '</span>');
						}
						return children;
					}
				}
			);

			return this;
		},
		saveModel: function(e) {
			e.preventDefault();
			this.startLoadingFull();
			this.model.save({
				name: this.$('#name').val(),
				stub: this.$('#stub').val(),
				tags: this.$('#tags').data('tags')
			}, {
				success: _.bind(this.saveOk, this),
				error: _.bind(this.loadingError, this)
			});
		},
		saveOk: function() {
			context.navigate("/workspace/list");
		},
		events: {
			"click button.submit": "saveModel",
		}
	});

	return WorkspaceEditView;
});
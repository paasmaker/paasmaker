/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.workspace) { pm.workspace = {}; }


pm.workspace.view = (function() {

	return {

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			
			var url_match = document.location.pathname.match(/\/(\d+)\//);
			pm.leftmenu.updateAppMenu(url_match[1]);
			
			pm.data.api({
				endpoint: 'workspace/' + url_match[1],	// or just document.location?
				callback: function(data) {
					$('#main_right_view').html(pm.handlebars.workspace_main(data));
					$('.loading-overlay').remove();
					pm.stats.workspace.redraw();

					pm.data.api({
						endpoint: 'job/list/workspace/' + url_match[1],
						callback: function(job_data) {
							pm.jobs.summary.show($('.workspace-overview .job-overview'), job_data.jobs.slice(0,5));
						}
					});
				}
			});
		}

	};
}());


pm.workspace.edit = (function() {
	var form_submit_url;

	return {

		drawForm: function(data) {
			$('#main_right_view').html(pm.handlebars.workspace_edit(data));
			
			if (data.workspace.id !== null) {
				pm.leftmenu.updateBreadcrumbs({
					workspace: data.workspace, suffix: "Edit Workspace"
				});
			}
			
			if (data.workspace.id === null) {
				// when creating a workspace (i.e. stub is empty), auto-generate stub from the name
				pm.workspace.edit.nameChanged();
				$('#workspace_name').on('keyup', pm.workspace.edit.nameChanged);
				$('#workspace_stub').on('keyup', function() {
					if ($('#workspace_stub').val() !== pm.workspace.edit.generateStub($('#workspace_name').val())) {
						// if user edits the stub to something other than what we'd generate,
						// stop auto-updating so we don't clobber their edit
						$('#workspace_name').off('keyup', pm.workspace.edit.nameChanged);
					}
				});
			}
			
			// TODO: a proper loader for the JS plugin and for the extra CSS file
			$('head').append('<link rel="stylesheet" href="/static/css/tag_editor.css">');
			pm.workspace.edit.jsonEditor(data.workspace.tags);
			
			$('.loading-overlay').remove();
		},

		newWorkspaceForm: function() {
			form_submit_url = 'workspace/create';
			
			// when creating a new workspace, showing the menu of
			// another makes no sense; TODO: maybe use a modal
			$("#left_menu_wrapper").empty();
			
			pm.data.api({
				endpoint: 'workspace/list',
				callback: function(data) {
					var new_name = "New Workspace";
					var valid_name = false;
					
					while (!valid_name) {
						for (var i = 0, workspace; workspace = data.workspaces[i]; i++) {
							if (workspace.name == new_name) {
								var name_match = new_name.match(/^(.+) (\d+)$/);
								if (name_match) {
									new_name = name_match[1] + ' ' + (parseInt(name_match[2]) + 1);
								} else {
									new_name += " 1";
								}
								valid_name = false;
								break;
							} else {
								valid_name = true;
							}
						}
					}
									
					pm.workspace.edit.drawForm({
						workspace: {
							id: null,
							name: new_name,
							tags: {}
						}
					});
				}
			});
		},

		jsonEditor: function(values) {
			$('.workspace-tag-editor').jsonEditor({ Tags: values }, {
				newSingleKey: "New Tag",
				newGroupKey: "Tag Group",
				change: function(new_obj) {
					$('#workspace_tags').val(JSON.stringify(new_obj.Tags));
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
			});
		},

		generateStub: function(name) {
			return name.replace(/[^a-zA-Z0-9]/g, '');
		},
		
		nameChanged: function() {
			$('#workspace_stub').val(
				pm.workspace.edit.generateStub($('#workspace_name').val())
			);
		},

		actionButton: function(e) {
			pm.history.loadingOverlay("#main_right_view");
			$("div.alert").remove();
			
			pm.data.post({
				endpoint: form_submit_url,
				body_data: $('form.workspace-edit').serialize(),
				errorCallback: function(response) {
					response.errors.forEach(function(error) {
						$('form.workspace-edit').before(
							$("<div class=\"alert\">" + error + "</div>")
						);
					});
					$('.loading-overlay').remove();
				},
				callback: function(response) {
					window.history.pushState({ handle_in_js: true }, '', "/workspace/" + response.data.workspace.id + "/applications");
					pm.workspace.view.switchTo();
				}
			});
		},

		switchTo: function() {
			pm.leftmenu.redrawContainers();
			
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);
			
			if (url_match) {
				pm.leftmenu.updateAppMenu(url_match[1]);
				form_submit_url = 'workspace/' + url_match[1];
				
				pm.data.api({
					endpoint: 'workspace/' + url_match[1],	// or just document.location?
					callback: pm.workspace.edit.drawForm
				});
				
			} else {
				pm.workspace.edit.newWorkspaceForm();
			}
		}

	};
}());

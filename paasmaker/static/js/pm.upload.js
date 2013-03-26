/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.upload.js - interface for uploading/updating an application
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.upload = (function() {

	return {
	
		// copy from script.js: if scm list plugins are enabled, load their output
		loadRepositoryLists: function() {
			$('.scm-list').each(
				function(index, element)
				{
					var el = $(element);
					var plugin = el.attr('data-plugin');
					$.getJSON(
						'/scm/list/repos?plugin=' + escape(plugin),
						function(data, text, xhr)
						{
							el.empty();
							el.append($('<option value="">Select...</option>'));
							for(var i = 0; i < data.data.repositories.length; i++ )
							{
								var entry = data.data.repositories[i];
								var op = $('<option></option>');
								op.text(entry.title);
								op.val(entry.url);

								el.append(op);
							}
						}
					);
					el.change(
						function(e)
						{
							// TODO: This assumes a lot about the HTML.
							var inner = el.parent().parent();
							var location = $('input.lister-target', $(inner));
							location.val(el.val());
						}
					);
				}
			);
		},

		actionButton: function(e) {
			// this code mostly duplicated with pm.version.js
			var parent_form = $(e.target).parents('form');
		
			pm.history.loadingOverlay("#main_right_view");
			pm.data.post({
				endpoint: document.location.pathname,
				body_data: $(parent_form).serialize(),
				callback: function(data) {
					$('.loading-overlay').remove();
					
					// pushState so the Back button works, but TODO: this should be in pm.history?
					var state = { job_id: data.job_id }, url_match;
					url_match = document.location.pathname.match(/\/application\/(\d+)\/newversion/);
					if (url_match) {
						state.application_id = url_match[1];
					} else {
						url_match = document.location.pathname.match(/\/workspace\/(\d+)\/applications\/new/);
						state.workspace_id = url_match[1];
					}
					
					window.history.pushState({ handle_in_js: true }, '', "/job/detail/" + data.job_id);
					pm.jobs.version_action.switchTo(state);
				}
			});
		},

		switchTo: function() {
			var url_match, form_fetch_url, suffix;
			var parent_search = {}, menu_highlight = {};
			url_match = document.location.pathname.match(/\/workspace\/(\d+)\/applications\/new/);
			if (url_match) {
				form_fetch_url = url_match[0];
				parent_search.workspace_id = url_match[1];
				menu_highlight.newApplication = true;
				suffix = "New Application";
			} else {
				url_match = document.location.pathname.match(/\/application\/(\d+)\/newversion/);
				if (!url_match) { console.log("pm.upload controller called with invalid URL"); return false; }
				form_fetch_url = url_match[0]
				parent_search.application_id = url_match[1];
				menu_highlight.application = url_match[1];
				suffix = "New Version";
			}

			if ($('#left_menu_wrapper').length && $('#main_right_view').length) {
				$('#main_right_view').empty();
			} else {
				$('#main').empty();
				$('#main').append(
					$("<div id=\"left_menu_wrapper\">"),
					$("<div id=\"main_right_view\" class=\"with-application-list\">")
				);
				//pm.history.loadingOverlay("#main_right_view");
			}

			parent_search.callback = function(parents) {
				pm.workspace.updateAppMenu(parents.workspace.id, menu_highlight);
				pm.application.updateBreadcrumbs({
					workspace: parents.workspace,
					application: parents.application,
					suffix: suffix
				});
			};

			$.ajax({
				dataType: 'html',
				type: 'get',
				url: form_fetch_url + '?raw=true',
				success: function(form_string) {
					$('#main_right_view').html(form_string);

					$('.scm-container li a:first').tab('show');
					$('.scm-container li a').click(function(e) {
						e.preventDefault();
						$(e.target).tab('show');
					})

					$('.file-uploader-widget').each(function(i, element) {
						new pm.widgets.upload($(element));
					});

					pm.upload.loadRepositoryLists();
					pm.data.get_app_parents(parent_search);
					$('.loading-overlay').remove();
				}
			});
		}

	};
}());

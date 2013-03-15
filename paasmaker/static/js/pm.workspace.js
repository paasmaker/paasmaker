/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.workspace.js - interface for viewing a workspace
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.workspace = (function() {
	var workspaceViewTemplate =
		"<div id=\"applications\"><ul>"
		+ "{{#each data.applications}}"
			+ "<li><a href=\"/application/{{id}}\">{{name}} [{{health}}]</a></li>"
		+ "{{/each}}"
		+ "</ul></div>"
		+ "<div id=\"workspace\">"
			+ "<h1>{{data.workspace.name}}</h1>"
			+ "<div>Last updated {{data.workspace.updated}}</div>"
		+ "</div>";

	var workspaceView = Handlebars.compile(workspaceViewTemplate);

	return {

		draw: function(workspace_id) {
			pm.data.api({
			    endpoint: "workspace/" + workspace_id + "/applications",
				callback: function(data) {
					var contents = { list: $("<ul>"), data: data };
					data.applications.forEach(function(app) {
						contents.list.append(
							$("<li><a href=\"\">" + app.name + "</a></li>")
						);
					});
					$("#main").html(workspaceView(contents));
					// app_list.on('click', function(e) { console.log(e.target); });
				}
			});

		},

		// event handler for changes in the workspace switcher
		switchTo: function(e) {
			var workspace_id = $(e.target).val();

			console.log("Switching to " + workspace_id);

			if (workspace_id == "overview") {
				pm.overview.init();
			} else {
				// do stuff
				pm.workspace.draw(workspace_id);
			}
		}

	};
}());

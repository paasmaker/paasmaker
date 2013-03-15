/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * paasmaker.js - load page modules, fire off initial constructors/init calls
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

// do some module load-ey stuff

$(function() {
	// Page initialisation

	// Populate the workspaces dropdown.
	// TODO: Make this more efficient without having the server include it in the HTML.
	// NOTE: This doesn't handle errors - if you're not logged in, no list.
	// TODO: update list when workspaces are added/edited
	// var workspaceListContainer = $('.nav .workspace-list');
	pm.data.api({
	    endpoint: 'workspace/list',
		callback: function(data) {
			var menu = $("<select class=\"\"></select>");
			var optgroup = $("<optgroup label=\"Workspaces\">");
			menu.append(
	            $("<option value=\"overview\">Overview</option><option value=\"overview\"></option>")
            );
			menu.append(optgroup);
			data.workspaces.forEach(function(workspace) {
				optgroup.append(
					$("<option value=\"" + workspace.id + "\">" + workspace.name + "</option>")
				);
			});
			$("#workspace_switcher").empty();
			$("#workspace_switcher").append(menu);
			menu.on('change', pm.workspace.switchTo);
		}
	});

	// Holdover from previous interface: while loading, show a HTML5 feature report card
	// Code from Modernizr 2.6.2
	var tests = {
		"File API": function () { return !!(window.File && window.FileList && window.FileReader); },
		"Resumable library uploads": function () { var r = new Resumable(); return r.support; },
		"JSON parsing": function() { return (!!window.JSON && !!JSON.parse); },
		"History API": function() { return !!(window.history && history.pushState); },
		"Drag &amp; drop": function() { var div = document.createElement('div'); return ('draggable' in div) || ('ondragstart' in div && 'ondrop' in div); },
		"Web Sockets": function() { return 'WebSocket' in window || 'MozWebSocket' in window; }
	};

	var resultList = $('<ul></ul>');
	for (var test in tests) {
		var labels = { true: 'yes!', false: 'no :-(' };
		resultList.append($('<li>' + test + ': ' + labels[tests[test]()] + '</li>'));
	}
	$('#main').append('<p>For now, does your browser support things?</p>', resultList);

	// Load the overview dashboard
	// pm.overview.init();
});

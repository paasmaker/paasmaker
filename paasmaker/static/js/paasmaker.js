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

	// TODO: This connection timeout is low to force it to fallback to XHR quickly
	// when websocket fails. This may be too short though for production use.
	// Maybe we can more intelligently decide this and give socket.io a better hint?
	// var streamSocket = new io.connect(window.location.protocol + '//' + window.location.host, {'connect timeout': 1000});
	// streamSocket.on('disconnect',
	// 	function()
	// 	{
	// 		streamSocket.socket.reconnect();
	// 	}
	// );

	// Populate the workspaces dropdown.
	// TODO: Make this more efficient without having the server include it in the HTML.
	// NOTE: This doesn't handle errors - if you're not logged in, no list.
	// var workspaceListContainer = $('.nav .workspace-list');
	// if( workspaceListContainer.length > 0 )
	// {
	// 	$.getJSON(
	// 		'/workspace/list?format=json',
	// 		function(data, text, xhr) {
	// 			for (var i = 0; i < data.data.workspaces.length; i++) {
	// 				workspace = data.data.workspaces[i];
	// 				thisA = $('<a href="/workspace/' + workspace.id + '/applications"></a>');
	// 				thisA.text(workspace.name);
	// 				thisLi = $('<li></li>');
	// 				thisLi.append(thisA);
	// 				workspaceListContainer.append(thisLi);
	// 			}
	// 		}
	// 	);
	// }

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
});

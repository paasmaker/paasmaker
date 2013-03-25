
if (!window.pm) { var pm = {}; }	// TODO: module handling

// Load steps for the hybrid HTML/ajax web interface
$(function() {
	pm.history.init();
});

$(document).ready(
	function()
	{
		if( $('.workspace-tag-editor').length > 0 )			{
			var values = {Tags: JSON.parse($('#pm_workspace_tags').val())};

			console.log(this);
			$('.workspace-tag-editor').jsonEditor(values, {
				change: function(new_obj) {
					new_json = JSON.stringify(new_obj.Tags);
					$('#foobar-tag-debug').html(new_json);
					$('#pm_workspace_tags').val(new_json);
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
		}

		var testBrowserFeatures = function(resultContainer) {
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
			resultContainer.empty();
			resultContainer.append('<p>Feature tests for your browser:</p>', resultList);
		}

		if( $('#test-browser-features').length > 0 ) {
			testBrowserFeatures($('#test-browser-features'));
		}

		// set up the socket.io handler
		pm.data.initSocket();

		if( $('.job-root').length > 0 ) {
			$('.job-root').each(
				function(index, element) {
					new pm.jobs.display($(element));
				}
			);
		}

		// search the page for .router-stats, and set up the stats widget in any that we find
		// (no longer needed on ajax view pages like version list, but used on overview)
		pm.stats.routerstats.redraw();

		// Disable any disabled buttons.
		$('.btn.disabled').click(
			function(e)
			{
				e.preventDefault();
			}
		);

		// Populate the workspaces dropdown.
		// TODO: Make this more efficient without having the server include it in the HTML.
		// NOTE: This doesn't handle errors - if you're not logged in, no list.
		if ($('.nav .workspace-list').length) {
			pm.data.api({
				endpoint: 'workspace/list',
				callback: function(data) {
					data.workspaces.forEach(function(workspace) {
						var thisLi = $('<li>');
						thisLi.append($('<a href="/workspace/' + workspace.id + '/applications">' + workspace.name + '</a>'));
						$('.nav .workspace-list').append(thisLi);
					});
				}
			});
		}
		// Similarly, populate the nodes dropdown.
		if ($('.nav .node-list').length) {
			pm.data.api({
				endpoint: 'node/list',
				callback: function(data) {
					data.nodes.forEach(function(node) {
						var thisLi = $('<li>');
						thisLi.append($('<a href="/node/' + node.id + '">' + node.name + '</a>'));
						$('.nav .node-list').append(thisLi);
					});
				}
			});
		}

	}
)

// Helper functions.

// From: http://stackoverflow.com/questions/1219860/javascript-jquery-html-encoding
// TODO: Reconsider if this is appropriate.
function htmlEscape(str) {
		return String(str)
						.replace(/&/g, '&amp;')
						.replace(/"/g, '&quot;')
						.replace(/'/g, '&#39;')
						.replace(/</g, '&lt;')
						.replace(/>/g, '&gt;');
}
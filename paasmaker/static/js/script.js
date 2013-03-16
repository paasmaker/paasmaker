
if (!window.pm) { var pm = {}; }	// TODO: module handling

function testBrowserFeatures(resultContainer)
{
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

$(document).ready(
	function()
	{
		if( $('.workspace-tag-editor').length > 0 )
		{
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

		if( $('#test-browser-features').length > 0 ) {
			testBrowserFeatures($('#test-browser-features'));
		}

		if( $('.file-uploader-widget').length > 0 )
		{
			$('.file-uploader-widget').each(
				function(index, element)
				{
					new pm.widgets.upload($(element));
				}
			);
		}

		// TODO: This connection timeout is low to force it to fallback to XHR quickly
		// when websocket fails. This may be too short though for production use.
		// Maybe we can more intelligently decide this and give socket.io a better hint?
		streamSocket = new io.connect(window.location.protocol + '//' + window.location.host, {'connect timeout': 1000});
		streamSocket.on('disconnect',
			function()
			{
				streamSocket.socket.reconnect();
			}
		);

		if( $('.job-root').length > 0 )
		{
			$('.job-root').each(
				function(index, element)
				{
					new pm.jobs.display($(element), streamSocket);
				}
			);
		}
		if( $('.instance-log-container').length > 0 )
		{
			$('.instance-log-container').each(
				function(index, element)
				{
					new pm.logs.instance(streamSocket, $(element).attr('data-instance'));
				}
			);
		}

		if( $('.router-stats').length > 0 )
		{
			$('.router-stats').each(
				function(index, element)
				{
					element = $(element);
					pm.stats.routerstats.stats(streamSocket, element, element.data('name'), element.data('inputid'), element.data('title'));
				}
			);
		}

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
		var workspaceListContainer = $('.nav .workspace-list');
		if( workspaceListContainer.length > 0 )
		{
			$.getJSON(
				'/workspace/list?format=json',
				function(data, text, xhr)
				{
					for( var i = 0; i < data.data.workspaces.length; i++ )
					{
						workspace = data.data.workspaces[i];
						thisA = $('<a href="/workspace/' + workspace.id + '/applications"></a>');
						thisA.text(workspace.name);
						thisLi = $('<li></li>');
						thisLi.append(thisA);
						workspaceListContainer.append(thisLi);
					}
				}
			);
		}

		// On the new applications page, collapse the options until you click one.
		var scms = $('.scm-container');
		if( scms.length > 0 )
		{
			$('.scm', scms).not('.scm-active').each(
				function(index, element)
				{
					var el = $(element);
					var inner = $('.inner', el);
					inner.hide();
					var show = $('<a href="#"><i class="icon-plus-sign"></i> Show...</a>');
					show.click(
						function(e)
						{
							inner.show();
							show.hide();
							e.preventDefault();
						}
					);
					el.append(show);
				}
			);

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
							var inner = el.parent();
							var location = $('input.lister-target', $(inner));
							location.val(el.val());
						}
					);
				}
			);
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
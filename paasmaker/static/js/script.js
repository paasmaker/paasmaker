
if (!window.pm) { var pm = {}; }	// TODO: module handling

function testBrowserFeatures(resultContainer)
{
	resultContainer.empty();

	resultList = $('<ul></ul>');

	var reportResult = function(name, result)
	{
		resultLabel = result ? 'Success' : 'Failure';
		resultList.append($('<li>' + name + ': ' + resultLabel + '</li>'));
	}

	reportResult("Websockets", Modernizr.websockets);

	var r = new Resumable();

	reportResult("HTML5 File uploads", r.support);

	resultContainer.append(resultList);
}

$(document).ready(
	function()
	{
		if( $('.workspace-tag-editor').length > 0 )
		{
			new pm.widgets.tag_editor($('form'), $('.workspace-tag-editor'));
		}

		if( $('.test-browser-features').length > 0 )
		{
			testBrowserFeatures($('.test-browser-features'));
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
		var streamSocket = new io.connect(window.location.protocol + '//' + window.location.host, {'connect timeout': 1000});
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
					new pm.stats.router(streamSocket, $(element));
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
// number_format from: http://phpjs.org/functions/number_format/
function number_format (number, decimals, dec_point, thousands_sep) {
  number = (number + '').replace(/[^0-9+\-Ee.]/g, '');
  var n = !isFinite(+number) ? 0 : +number,
    prec = !isFinite(+decimals) ? 0 : Math.abs(decimals),
    sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep,
    dec = (typeof dec_point === 'undefined') ? '.' : dec_point,
    s = '',
    toFixedFix = function (n, prec) {
      var k = Math.pow(10, prec);
      return '' + Math.round(n * k) / k;
    };
  // Fix for IE parseFloat(0.55).toFixed(0) = 0;
  s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
  if (s[0].length > 3) {
    s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
  }
  if ((s[1] || '').length < prec) {
    s[1] = s[1] || '';
    s[1] += new Array(prec - s[1].length + 1).join('0');
  }
  return s.join(dec);
}

// From: http://stackoverflow.com/questions/661562/how-to-format-a-float-in-javascript
function toFixed(value, precision) {
    var power = Math.pow(10, precision || 0);
    return (Math.round(value * power) / power).toFixed(precision);
}

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
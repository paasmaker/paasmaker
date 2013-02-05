
if (!window.pm) { var pm = {}; }	// TODO: module handling

var WebsocketHandler = function(endpoint)
{
	var _self = this;
	this.connected = false;
	this.connecting = false;
	this.endpoint = endpoint;
	this.mode = 'auto';

	this._queue = [];
}

WebsocketHandler.prototype.connect = function()
{
	// Don't try to connect if we're in longpoll mode.
	if(this.mode != 'auto' && this.mode != 'websocket')
	{
		return;
	}
	if(this.connected || this.connecting)
	{
		return;
	}

	this.connecting = true;
	var _self = this;
	this.websocket = new WebSocket(this.getWebsocketUrl());
	this.websocket.onopen = function()
	{
		_self.connected = true;
		_self.connecting = false;
		_self.mode = 'websocket';

		// Send along the contents of the queue.
		var thisQueue = _self._queue;
		_self._queue = [];
		for(var i = 0; i < thisQueue.length; i++)
		{
			_self.send(thisQueue[i]);
		}

		_self.onopen();
	};
	this.websocket.onmessage = function(evt)
	{
		//console.log(evt.data);
		_self.onmessage($.parseJSON(evt.data), evt);
	}
	this.websocket.onerror = function(evt)
	{
		//console.log("Error");
		//console.log(evt);

		// Switch between 'not supported' and 'disconnected'.
		// TODO: Find a reliable way to do this.
		// For now, we assume that if we previously connected
		// as a websocket, then it's supported. Otherwise, switch
		// to longpoll.

		this.connected = false;
		this.connecting = false;

		if(_self.mode == 'auto')
		{
			// Websockets not supported. Fallback to long poll mode.
			_self.mode = 'longpoll';
			_self.doLongPoll();
		}
		else
		{
			// Retry connection shortly.
			setTimeout(
				function()
				{
					_self.connect();
				},
				1000
			);
		}
	}

	this.websocket.onclose = function(evt)
	{
		// Remote end closed.
		// Wait a second, and then try again.
		setTimeout(
			function()
			{
				_self.connect();
			},
			1000
		);
	}
}

WebsocketHandler.prototype.getWebsocketUrl = function()
{
	return "ws://" + window.location.host + this.endpoint;
}

WebsocketHandler.prototype.onmessage = function(data, evt)
{
	//console.log("onmessage() not implemented.");
	//console.log(data);
	//console.log(evt);
}

WebsocketHandler.prototype.onopen = function()
{
}

WebsocketHandler.prototype.onerror = function()
{
	// Handle your errors here.
}

WebsocketHandler.prototype.send = function(message)
{
	if(this.connected && this.mode == 'websocket')
	{
		this.websocket.send($.toJSON(message));
	}
	else
	{
		this._queue.push(message);

		if(this.mode == 'longpoll')
		{
			// Send it off to the server.
			this.doLongPoll(this.connected);
		}
	}
}

WebsocketHandler.prototype.doLongPoll = function(sendOnly)
{
	// Force convert to a boolean.
	// TODO: Oh, the hacks.
	sendOnly = !!sendOnly;

	if(this.connected && !sendOnly)
	{
		// Already connected, and not sending only.
		// Take no action here.
		return;
	}
	if(this.connected && !this.session_id)
	{
		// No session ID yet, but we have a request in progress.
		// Just queue the request, because we don't want
		// to double up on session IDs.
		return;
	}
	if(!this.connected && sendOnly)
	{
		// We're not currently connected, but are sending
		// only. So make this request not-sendOnly.
		sendOnly = false;
	}

	// Not connected - send along the data.
	if(!sendOnly)
	{
		this.connected = true;
	}

	// Get all entries on the queue right now.
	var thisQueue = this._queue;
	// Empty it out.
	this._queue = [];

	var _self = this;
	var body = {
		data: {
			endpoint: _self.endpoint,
			commands: thisQueue,
			send_only: sendOnly
		}
	};

	// Send along the session ID, if we have one.
	if(this.session_id)
	{
		body.data.session_id = this.session_id;
	}

	$.ajax(
		// Adding 'endpoint=' is purely to assist debugging in the log files.
		'/websocket/longpoll?format=json&endpoint=' + escape(_self.endpoint),
		{
			type: 'POST',
			data: $.toJSON(body),
			success: function(data)
			{
				// Send along all the messages.
				for(var i = 0; i < data.data.messages.length; i++)
				{
					var thisMessage = data.data.messages[i];
					if(thisMessage.session_id && !_self.session_id)
					{
						_self.session_id = thisMessage.session_id;
						console.log("Endpoint " + _self.endpoint + " sid " + _self.session_id);
					}
					else
					{
						_self.onmessage(thisMessage);
					}
				}

				if(!sendOnly)
				{
					// Start long polling again.
					_self.connected = false;
					_self.doLongPoll();
				}
			},
			error: function(xhr, status, error)
			{
				_self.connected = false;

				if(xhr.status == 400)
				{
					// Bad session ID. Clear it and
					// create a new session.
					_self.session_id = false;
					_self.doLongPoll();
				}
				else
				{
					// It didn't work.
					console.log(xhr);
					console.log(status);
					console.log(error);

					_self.onerror();

					// Put the messages back onto the queue.
					_self._queue = thisQueue.concat(_self._queue);

					// Try again in a short while.
					setTimeout(
						function()
						{
							_self.doLongPoll(false);
						},
						1000
					);
				}
			}
		}
	);
}

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

		var jobStream = new pm.jobs.stream();
		var logStream = new pm.logs.stream();
		if( $('.job-root').length > 0 )
		{
			$('.job-root').each(
				function(index, element)
				{
					new pm.jobs.display($(element), jobStream, logStream);
				}
			);
		}
		if( $('.instance-log-container').length > 0 )
		{
			$('.instance-log-container').each(
				function(index, element)
				{
					new pm.logs.instance(logStream, $(element).attr('data-instance'));
				}
			);
		}

		if( $('.router-stats').length > 0 )
		{
			$('.router-stats').each(
				function(index, element)
				{
					new pm.stats.router($(element));
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
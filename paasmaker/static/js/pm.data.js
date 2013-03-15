/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.data.js - wrapper to manage Web Sockets and JSON API calls from frontend code
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

// For short-term compatibility, keep this as a global object.
// Later we can make it private and require the use of getSocket.
var streamSocket;

pm.data = (function() {

	return {

		/**
		 * Very simple wrapper for calls to the pacemaker's JSON API:
		 *  - appends ?format=json so other code doesn't need to
		 *  - parses JSON and gets out the .data property
		 *  - detects (but doesn't yet handle) errors and warnings
		 *
		 * @param options object with these properties:
		 *  - endpoint: URL of the API endpoint to call
		 *  - callback: function to call when request completes
		 *  - arguments: (optional) key-value mapping of arguments to append to the URL
		 *  - warningCallback: (optional) function to call when API returns a warning
		 *  - errorCallback: (optional) function to call when API returns an error
		 */
		api: function(options) {
			if (!options.arguments) { options.arguments = {}; }

			if (options.endpoint.indexOf('?') !== -1) {
				// parse out existing arguments if there are any in the endpoint string
				var query_string = options.endpoint.split('?');
				options.endpoint = query_string[0];

				query_string.split('&').forEach(function(arg) {
					arg_parts = arg.split('=');
					options.arguments[decodeURIComponent(arg_parts[0])] = decodeURIComponent(arg_parts[1]);
				});
			}

			// make sure ?format=json is included, then rebuild the query string
			options.arguments[format] = "json";
			var arg_string = '';
			for (var key in options.arguments) {
				arg_string += encodeURIComponent(key) + '=' + encodeURIComponent(options.arguments[key]);
			}

			$.getJSON(
				options.endpoint + '?' + arg_string,
				function(responseData) {
					if (responseData.errors && responseData.errors.length > 0) {
						console.log("API call to " + endpoint + " returned an error!");
						console.log(responseData.errors);
						if (options.errorCallback) {
							options.errorCallback.apply(this, arguments);
						}
					}
					if (responseData.warnings && responseData.warnings.length > 0) {
						console.log("WARNING WARNING: API call to " + endpoint + " returned a warning!");
						console.log(responseData.warnings);
						if (options.warningCallback) {
							options.warningCallback.apply(this, arguments);
						}
					}

					// make sure other arguments are passed unchanged
					var modified_args = arguments;
					modified_args[0] = responseData.data;

					options.callback.apply(this, modified_args);
				}
			);
		},

		// Preferred method for getting access to the socket.io connection object
		getSocket: function() {
			return streamSocket;
		},

		emit: function() {
			pm.data.getSocket().emit.apply(streamSocket, arguments);
		},

		subscribe: function(eventName, callback, capture) {
			pm.data.getSocket().on(
				eventName,
				function() {
					callback.apply(streamSocket, arguments);
				},
				capture
			);
		},

		init: function() {

			// Set up the web socket for getting stats, job, and other data
			// from the pacemaker (or long poll -- handled by socket.io)
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

		}

	};
}());

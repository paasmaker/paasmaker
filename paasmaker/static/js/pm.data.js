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
		 * Wrapper for GET calls to the pacemaker's JSON API:
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

			if (options.endpoint.substr(0, 1) !== '/') {
				options.endpoint = '/' + options.endpoint;
			}

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
			options.arguments.format = "json";
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

		/**
		 * Wrapper for POST calls to the pacemaker's JSON API:
		 *  - appends ?format=json so other code doesn't need to
		 *  - parses JSON and gets out the .data property
		 *  - detects (but doesn't yet handle) errors and warnings
		 *
		 * @param options object with these properties:
		 *  - endpoint: URL of the API endpoint to call
		 *  - callback: function to call when request completes
		 *  - body_data: (optional) string to pass into POST body
		 *  - arguments: (optional) key-value mapping of arguments to append to the URL
		 *  - warningCallback: (optional) function to call when API returns a warning
		 *  - errorCallback: (optional) function to call when API returns an error
		 */
		post: function(options) {
			// TODO: this code is duplicated above
			if (!options.arguments) { options.arguments = {}; }
			if (!options.body_data) { options.body_data = {}; }

			if (options.endpoint.substr(0, 1) !== '/') {
				options.endpoint = '/' + options.endpoint;
			}

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
			options.arguments.format = "json";
			var arg_string = '';
			for (var key in options.arguments) {
				arg_string += encodeURIComponent(key) + '=' + encodeURIComponent(options.arguments[key]);
			}

			$.post(
				options.endpoint + '?' + arg_string,
				options.body_data,
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

					if (responseData.success) {
						var modified_args = arguments;
						modified_args[0] = responseData;
						options.callback.apply(this, modified_args);
					}
				},
				"json"
			);
		},

		/**
		 * Convenience wrapper around pm.data.api for simple API calls that just
		 * need their output directly rendered with a particular Handlebars template.
		 *
		 * @param options object with these properties:
		 *  - endpoint: URL of the API endpoint to call
		 *  - template: compiled Handlebars template to use
		 *  - element: element in which to render the template
		 *  - callback: optional callback to run after rendering
		 */
		template_from_api: function(options) {
			pm.data.api({
				endpoint: options.endpoint,
				callback: function(data) {
					$(options.element).html(
						options.template.apply(this, [data])
					);

					if (options.callback) {
						options.callback.apply(this, [data]);
					}
				}
			});
		},

		/**
		 * Convenience wrapper to get the parent objects of an application or version when
		 * showing a detail view in the interface (e.g. for menus and breadcrumbs).
		 *
		 * @param options object with these properties:
		 *  - application_id or version_id: database ID of the object to fetch parents for
		 *  - callback: function to run with output value as the only argument. Output value
		 *    is an object with properties workspace, application, and optionally version
		 *    each corresponding to the objects returned by the API.
		 */
		get_app_parents: function(options) {
			var retval = {};

			var version_received = function(data) {
				retval.version = data.version;
				get_application(data.version.application_id);
			}
			var application_received = function(data) {
				retval.application = data.application;
				get_workspace(data.application.workspace_id);
			}
			var workspace_received = function(data) {
				retval.workspace = data.workspace;
				options.callback.apply(this, [retval]);
			}

			get_version = function(id) {
				pm.data.api({
					endpoint: 'version/' + id,
					callback: version_received
				});
			}
			get_application = function(id) {
				pm.data.api({
					endpoint: 'application/' + id,
					callback: application_received
				});
			}
			get_workspace = function(id) {
				pm.data.api({
					endpoint: 'workspace/' + id,
					callback: workspace_received
				});
			}

			if (options.version_id) {
				get_version(options.version_id);
			} else if (options.application_id) {
				get_application(options.application_id);
			} else if (options.workspace_id) {
				get_workspace(options.workspace_id);
			}
		},

		// Preferred method for getting access to the socket.io connection object
		getSocket: function() {
			return streamSocket;
		},

		removeListeners: function() {
			if (pm.data.getSocket()) {
				pm.data.getSocket().removeAllListeners();
			}
		},

		emit: function() {
			// console.log('pm.data.emit:', arguments);
			pm.data.getSocket().emit.apply(streamSocket, arguments);
		},

		subscribe: function(eventName, callback, capture) {
			// console.log('pm.data.subscribe on ' + eventName);
			pm.data.getSocket().on(
				eventName,
				function() {
					callback.apply(streamSocket, arguments);
				},
				capture
			);
		},

		initSocket: function() {

			// Set up the web socket for getting stats, job, and other data
			// from the pacemaker (or long poll -- handled by socket.io)
			// TODO: This connection timeout is low to force it to fallback to XHR quickly
			// when websocket fails. This may be too short though for production use.
			// Maybe we can more intelligently decide this and give socket.io a better hint?
			streamSocket = new io.connect(window.location.protocol + '//' + window.location.host, {'connect timeout': 1000});
			streamSocket.on('disconnect', function() {
				streamSocket.socket.reconnect();
			});

		}

	};
}());

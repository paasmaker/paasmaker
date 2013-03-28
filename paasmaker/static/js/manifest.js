/* Paasmaker - Platform as a Service
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/**
 * Application manifest editor
 */

//----------------------------------------

if (!window.pm) { var pm = {}; }	// TODO: module handling

//----------------------------------------
// http://stackoverflow.com/a/6713782

Object.equals = function( x, y ) {
  if ( x === y ) return true;
  if ( ! ( x instanceof Object ) || ! ( y instanceof Object ) ) return false;
  if ( x.constructor !== y.constructor ) return false;

  for ( var p in x ) {
    if ( ! x.hasOwnProperty( p ) ) continue;
    if ( ! y.hasOwnProperty( p ) ) return false;
    if ( x[ p ] === y[ p ] ) continue;
    if ( typeof( x[ p ] ) !== "object" ) return false;
    if ( ! Object.equals( x[ p ],  y[ p ] ) ) return false;
  }

  for ( p in y ) {
    if ( y.hasOwnProperty( p ) && ! x.hasOwnProperty( p ) ) return false;
  }
  return true;
}

//----------------------------------------

var widget_counter = 0;	// TODO: deglobalise and/or just use widget_stack.length

var draw_functions = {
	manifest: function(structure, path) {
		return "<p>I am a manifest, format version: " + structure.format + "</p>";
	},

	application: function(structure, path) {
		var html = "<div class=\"pm-manifest-item pm-manifest-instance\" style=\"border:solid 1px green\">";
		html += "<h3>application: " + structure.name + "</h3>";
		if (structure.tags) {
			var div_id = widget_counter;
			html += "<input type=\"text\" id=\"pm-manifest-tags-" + div_id + "\"><div class=\"pm-tag-editor\" id=\"pm-manifest-widget-" + div_id + "\"></div>";
			widget_counter ++;

			var tag_editor_opts = {
				change: function() {
					return function(new_obj) {
						new_json = JSON.stringify(new_obj.Tags);
						$('#pm-manifest-tags-' + div_id).val(new_json);
					}
				}(),
				drawproperty: function(opt, json, root, path, key) {
					children = {};
		            if (key == 'Tags' && Object.prototype.toString.call(json[key]) == '[object Object]') {
						children.item = $('<div>', { 'class': 'item', 'data-path': path });
	                    children.item.addClass('expanded group-top-level');
	                    children.property = $(opt.headerElement || '<span class="property group-header">' + key + '</span>');
	                }
		            return children;
		        }
			};
			pm.manifest.add_widget('#pm-manifest-widget-' + div_id, 'jsonEditor', [{Tags: structure.tags}, tag_editor_opts]);
			pm.manifest.add_widget('#pm-manifest-tags-' + div_id, 'val', [JSON.stringify(structure.tags)]);
		}

		if (structure.prepare && structure.prepare.commands) {
			if (typeof structure.prepare.commands != "object" || typeof structure.prepare.commands.length != "number") {
				throw {
					problem: "Invalid format for prepare commands; should be a list of plugin definitions",
					problemMark: { line: pm.manifest.findLineNumber(path.concat(['prepare', 'commands'])) }
				};
			}
			html += "<h3>Prepare commands</h3>";
			structure.prepare.commands.forEach(function(list_item, i) {
				html += draw_functions.plugin(list_item, path.concat(['prepare', 'commands', i]));
			});
		}
		html += "</div>";
		return html;
	},

	instance: function(structure, path) {
		var html = "<div class=\"pm-manifest-item pm-manifest-instance\" style=\"border:solid 1px red\">";
		html += "<h3>instance: " + structure.name + "</h3>";
		if (structure.quantity) {	// TODO: is this required?
			html += "<p>quantity: " + structure.quantity + "</p>";
		}
		if (structure.runtime) {
			html += "<h3>Runtime</h3>";
			html += draw_functions.plugin(structure.runtime, path.concat(['runtime']));
		}
		if (structure.startup) {
			html += "<h3>Startup plugin</h3>";
			if (typeof structure.startup != "object" || typeof structure.startup.length != "number") {
				throw {
					problem: "Invalid format for startup commands; should be a list of plugin definitions",
					problemMark: { line: pm.manifest.findLineNumber(path.concat(['startup'])) }
				};
			}
			structure.startup.forEach(function(list_item, i) {
				html += draw_functions.plugin(list_item, path.concat(['startup', i]));
			});
		}
		if (structure.placement) {
			html += "<h3>Placement plugin</h3>";
			html += draw_functions.plugin(structure.placement, path.concat(['placement']));
		}
		if (structure.hostnames) {
			if (typeof structure.hostnames != "object" || typeof structure.hostnames.length != "number") {
				throw {
					problem: "Invalid format for instance hostnames; should be a list of strings",
					problemMark: { line: pm.manifest.findLineNumber(path.concat(['hostnames'])) }
				};
			}

			html += "<p>Hostnames for this instance: ";
			html += pm.manifest.form.string_list(structure.hostnames, path.concat(['hostnames']));
		}
		if (structure.crons) {
			if (typeof structure.crons != "object" || typeof structure.crons.length != "number") {
				throw {
					problem: "Invalid format for instance cron jobs; should be a list of runspec/uri pairs",
					problemMark: { line: pm.manifest.findLineNumber(path.concat(['crons'])) }
				};
			}
			html += "<h3>Cron jobs</h3>";
			structure.crons.forEach(function(list_item, i) {
				html += pm.manifest.form.cron(list_item, path.concat(['crons', i]));
			});
		}
		html += "</div>";
		return html;
	},

	instances: function(structure, path) {
		if (typeof structure != "object" || typeof structure.length != "number") {
			throw {
				problem: "Invalid format for instances section; should be a list of definitions for each instance",
				problemMark: { line: pm.manifest.findLineNumber(path) }
			};
		}

		var html = "<div><h3>Instances</h3>";
		structure.forEach(function(list_item, i) {
			html += draw_functions.instance(list_item, path.concat([i]));
		});
		html += "</div>";
		return html;
	},

	plugin: function(structure, path) {
		if (!structure.plugin) {
			throw {
				problem: "Plugin definition is missing symbolic name of plugin to load",
				problemMark: { line: pm.manifest.findLineNumber(path) }
			};
		}

		var html = "<fieldset class=\"pm-manifest-item pm-manifest-plugin\">";
		if (structure.name) {
			html += "<legend>plugin: " + structure.name + "</legend>";
		}
		html += "<p>provider: " + pm.manifest.form.plugin_dropdown(structure.plugin, null, path) + "</p>";
		if (structure.version) {
			html += "<p>required version: " + structure.version + "</p>";
		}
		if (structure.parameters) {
			for (var param in structure.parameters) {
				html += "<p>" + param + ": ";
				if (typeof structure.parameters[param] == "object") {
					html += pm.manifest.form.string_list(structure.parameters[param], path.concat(['parameters', param]));
				} else {
					html += structure.parameters[param];
				}
				html += "</p>";
			}
		}
		html += "</fieldset>";
		return html;
	},

	services: function(structure, path) {
		if (typeof structure != "object" || typeof structure.length != "number") {
			throw {
				problem: "Invalid format for services section; should be a list of plugin definitions for each service",
				problemMark: { line: pm.manifest.findLineNumber(path) }
			};
		}

		var html = "<div><h3>Services</h3>";
		structure.forEach(function(list_item, i) {
			html += draw_functions.plugin(list_item, path.concat([i]));
		});
		html += "</div>";
		return html;
	}
}

//----------------------------------------

pm.manifest = (function() {
	var textarea = {
		styles: {
			fontSize: 13,
			lineHeight: 15
		}
	}

	var current_manifest;
	var widget_stack = [];

	return {
		findLineNumber: function(path) {
			var lines = $("#pm_manifest_yaml_block").val().split(/\n/);
			var search_term = path.pop();
			if (typeof search_term == 'number') {
				var search_number = search_term;
				search_term = path.pop();
			}

			var expected_indent = 2 * path.length;	// TODO: assumes two spaces per tab

			for (var n = 0; n < lines.length; n++) {
				if (lines[n].indexOf(search_term) !== -1) { console.log(lines[n].indexOf(search_term)); }
				if (lines[n].indexOf(search_term) !== -1 && lines[n].indexOf(search_term) === expected_indent) {
					if (search_number) {
						// if the last item in the path is a list index, find the line corresponding to that index
						var current_item = 0;
						while (current_item < search_number) {
							if (/^\s\-/.test(lines[n])) { current_item ++; }
							n ++;
						}
						return n + 2;	// TODO: assumes the error is one line below the searched-for path
					} else {
						return n + 1;
					}
				}
			}
		},

		draw: function(structure) {
			if (typeof structure !== 'object') {
				throw {
					problem: "No sections defined! You need to include manifest, application, and instances", // "(should be one of: " + Object.keys(draw_functions).join(', ') + ")",
					problemMark: { line: null }
				};
			}

			var html = "";
			for (var key in structure) {
				if(!draw_functions[key]) {
					throw {
						problem: "Invalid section type: " + key, // "(should be one of: " + Object.keys(draw_functions).join(', ') + ")",
						problemMark: { line: pm.manifest.findLineNumber([key]) }
					};
				}

				html += draw_functions[key](structure[key], [key]);
			}
			$("#pm_manifest_rendered").html(html);

			if (widget_stack.length > 0) {
				console.log(widget_stack);
				widget_stack.forEach(function(widget) {
					$(widget.element)[widget.function_name].apply($(widget.element), widget.arguments);
				});
				widget_stack = [];
			}

			// TODO: do this in CSS?
			var height = $("#pm_manifest_rendered").height();
			$("#pm_manifest_yaml_form").css({'height': height + 'px'});
			$("#pm_manifest_yaml_block").css({'height': height + 'px'});
		},

		add_widget: function(element, function_name, arguments) {
			widget_stack.push({
				element: element,
				function_name: function_name,
				arguments: arguments
			});
		},

		plugins: null,

		form: {
			cron: function(structure, path) {
		 		var html = "<p>";
		 		html += "Visit " + structure.uri + " on schedule " + structure.runspec;
		 		if (structure.username) {
		 			html += " with username " + structure.username;
		 		}
		 		if (structure.password) {
		 			html += " with password " + structure.password;
		 		}
		 		html += "</p>";

		 		return html;
			},

			plugin_dropdown: function(selected_plugin, mode, path) {
				if (!pm.manifest.plugins) {
					// ajax call to the plugin list isn't back yet, so draw a placeholder
					return "<span class=\"pm-bare-plugin-name\">"
						+ selected_plugin
						+ "</span>";
				}

				if (selected_plugin && pm.manifest.plugins[selected_plugin]) {
					selected_plugin = pm.manifest.plugins[selected_plugin];
				}

				var html = "<select>";
				var plugin_found_in_list = false;

				for (var plugin_name in pm.manifest.plugins) {
					var plugin = pm.manifest.plugins[plugin_name];
					if (selected_plugin && selected_plugin.modes) {
						var plugin_modes_match = false;

						plugin_compare:
						for (var i=0, m1; m1 = selected_plugin.modes[i]; i++) {
							for (var j=0, m2; m2 = plugin.modes[j]; j++) {
								if (m1 === m2) {
									plugin_modes_match = true;
									break plugin_compare;
								}
							}
						}

						if (!plugin_modes_match) { continue; }
					}

					html += "<option value=\"" + plugin_name + "\"";
					if (selected_plugin && plugin_name === selected_plugin.name) {
						html += " selected=\"selected\"";
						plugin_found_in_list = true;
					}
					html += ">" + plugin.title + " (" + plugin_name + ")</option>"
				}

				if (!plugin_found_in_list) {
					html += "<option value=\"" + selected_plugin + "\" selected=\"selected\">";
					html += selected_plugin + " (Not currently loaded)</option>";	// TODO: red highlights, etc
				}

				html += "</select>";
				return html;
			},

			string_list: function(structure, path) {
		 		var html = "<ul>";
		 		structure.forEach(function(item, i) {
		 			html += "<li>" + item + "</li>";
		 		});
		 		html += "</ul>";

		 		return html;
			}
		},

		addErrorMessage: function(line, message) {
			if (line !== null) {
				var error_top_position = 10 + line * textarea.styles.lineHeight - $('#pm_manifest_yaml_block').scrollTop();
				var marker = "&#9650; ";
				var cls = "pm-manifest-error pm-manifest-error-line";
			} else {
				var error_top_position = 10;
				var marker = "&#9642; ";
				var cls = "pm-manifest-error pm-manifest-error-general";
			}

			var error_block = $('#pm_manifest_yaml_form').append(
				"<div class=\"" + cls + "\""
				+ "style=\"top:" + error_top_position + "px\">"
				+ marker + message
				+ "</div>"
			);
		},

		renderYAML: function() {
			var edited_yaml = $("#pm_manifest_yaml_block").val();

			$("#pm_manifest_yaml_form .pm-manifest-error").remove();

			try {
				var manifest = jsyaml.load(edited_yaml);

				if (!Object.equals(manifest, current_manifest)) {
					pm.manifest.draw(manifest);
					current_manifest = manifest;
				}
			}
			catch (e) {
				console.log(e);

				var message = e.problem;
				if (e.context) { message += e.context; }
				pm.manifest.addErrorMessage(e.problemMark.line, message);
			}
		},

		setUpDisplay: function() {
			//$("#pm_manifest_yaml_block").css(textarea.styles);
			for (var styleName in textarea.styles) {
				$("#pm_manifest_yaml_block").css(styleName, textarea.styles[styleName] + "px");
			}
		},

		init: function() {
			pm.manifest.setUpDisplay();

			if ($("#pm_manifest_yaml_block").val() != '') {
				pm.manifest.renderYAML();
			}

			$("#pm_manifest_yaml_block").on("keyup", pm.manifest.renderYAML);

			$.getJSON(
				'/configuration/plugins?format=json',
				null,
				function(response) {
					pm.manifest.plugins = response.data.plugins;

					$('.pm-bare-plugin-name').each(function(i, el) {
						$(el).replaceWith(
							pm.manifest.form.plugin_dropdown(el.textContent, null, null)
						);
					});
				}
			);
		}
	};
}());

$(function() {
	pm.manifest.init()
});
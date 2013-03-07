/**
 * Paasmaker
 *
 * Application manifest editor
 */

//----------------------------------------

var manifest = {};

// manifest.manifest = function() {};
// manifest.manifest.prototype.format = 1;
// manifest.manifest.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item\">"
// 		+ "<h3>manifest</h3>"
// 		+ "<p>format: 1</p>"
// 		+ "</div>"
// 	);
// };

// manifest.application = function() {};
// manifest.application.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item\">"
// 		+ "<h3>manifest</h3>"
// 		+ "<p>format: 1</p>"
// 		+ "</div>"
// 	);
// };

// manifest.instances = function() {};
// manifest.instances.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item pm-manifest-instance-list\"></div>"
// 	);
// };

// manifest.instance = function() {};
// manifest.instance.prototype.name = "";
// manifest.instance.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item pm-manifest-instance\">"
// 		+ "<h3>instance: " + this.name + "</h3>"
// 		+ "</div>"
// 	);
// };

// manifest.services = function() {};
// manifest.services.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item pm-manifest-service-list\"></div>"
// 	);
// };

// manifest.service = function() {};
// manifest.service.prototype.name = "";
// manifest.service.prototype.draw = function(container) {
// 	$(container).append(
// 		"<div class=\"pm-manifest-item pm-manifest-service\">"
// 		+ "<h3>service: " + this.name + "</h3>"
// 		+ "</div>"
// 	);
// };

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

var draw_functions = {
	manifest: function(structure) {
		return "<p>I am a manifest, format version: " + structure.format + "</p>";
	},

	application: function(structure) {
		var html = "<div class=\"pm-manifest-item pm-manifest-instance\" style=\"border:solid 1px green\">";
		html += "<h3>application: " + structure.name + "</h3>";
		if (structure.prepare && structure.prepare.commands) {
			if (typeof structure.prepare.commands != 'array') {
				// throw error
			}
			html += "<h3>Prepare commands</h3>";
			structure.prepare.commands.forEach(function(list_item) {
				html += draw_functions.plugin(list_item);
			});
		}
		html += "</div>";
		return html;
	},

	instance: function(structure) {
		var html = "<div class=\"pm-manifest-item pm-manifest-instance\" style=\"border:solid 1px red\">";
		html += "<h3>instance: " + structure.name + "</h3>";
		if (structure.quantity) {	// TODO: is this required?
			html += "<p>quantity: " + structure.quantity + "</p>";
		}
		if (structure.runtime) {
			html += "<h3>Runtime</h3>";
			html += draw_functions.plugin(structure.runtime);
		}
		if (structure.startup) {
			html += "<h3>Startup plugin</h3>";
			if (typeof structure.startup != 'array') {
				// throw error
			}
			structure.startup.forEach(function(list_item) {
				html += draw_functions.plugin(list_item);
			});
		}
		if (structure.placement) {
			html += "<h3>Placement plugin</h3>";
			html += draw_functions.plugin(structure.placement);
		}
		html += "</div>";
		return html;
	},

	instances: function(structure) {
		if (typeof structure != 'array') {
			// throw error
		}

		var html = "<div><h3>Instances</h3>";
		structure.forEach(function(list_item) {
			html += draw_functions.instance(list_item);
		});
		html += "</div>";
		return html;
	},

	plugin: function(structure) {
		var html = "<div class=\"pm-manifest-item pm-manifest-plugin\">";
		if (structure.name) {
			html += "<h3>plugin: " + structure.name + "</h3>";
		}
		if (!structure.plugin) {
			// throw error
		}
		html += "<p>provider: <span class=\"pm-bare-plugin-name\">" + structure.plugin + "</span></p>";
		html += "</div>";
		return html;
	},

	services: function(structure) {
		if (typeof structure != 'array') {
			// throw error
		}

		var html = "<div><h3>Services</h3>";
		structure.forEach(function(list_item) {
			html += draw_functions.plugin(list_item);
		});
		html += "</div>";
		return html;
	}
}

//----------------------------------------


$(function() {
	var textarea = {
		styles: {
			fontSize: 13,
			lineHeight: 15
		}
	}

	var current_manifest;
	var plugins;

	var findLineNumber = function(label, level) {
		var spaces_per_tab = 2;
		var lines = $("#pm_manifest_yaml_block").val().split(/\n/);
		for (var n = 0; n < lines.length; n++) {
			if (lines[n].indexOf(label) !== -1 && lines[n].indexOf(label) === spaces_per_tab * level) {
				return n + 1;
			}
		}
	};

	var draw = function(structure) {
		var html = "";
		for (var key in structure) {
			if(!draw_functions[key]) {
				var line = findLineNumber(key, 0);
				throw {
					problem: "Invalid section type: " + key, // "(should be one of: " + Object.keys(draw_functions).join(', ') + ")",
					problemMark: { line: line, column: 0 }
				};
			}

			html += draw_functions[key](structure[key]);
		}
		$("#pm_manifest_rendered").html(html);

		// TODO: do this in CSS?
		var height = $("#pm_manifest_rendered").height();
		$("#pm_manifest_yaml_form").css({'height': height + 'px'});
		$("#pm_manifest_yaml_block").css({'height': height + 'px'});
	};

	var addErrorMessage = function(line, column, message) {
		if (line !== null) {
			var error_top_position = 10 + line * textarea.styles.lineHeight - $('#pm_manifest_yaml_block').scrollTop();
			var marker = "&#9650; ";
		} else {
			var error_top_position = 0;
			var marker = "&#9642; ";
		}

		var error_block = $('#pm_manifest_yaml_form').append(
			"<div class=\"pm-manifest-error\""
			+ "style=\"top:" + error_top_position + "px\">"
			+ marker + message
			+ "</div>"
		);
	};

	var renderYAML = function() {
		var edited_yaml = $("#pm_manifest_yaml_block").val();

		$("#pm_manifest_yaml_form .pm-manifest-error").remove();

		try {
			var manifest = jsyaml.load(edited_yaml);

			if (!Object.equals(manifest, current_manifest)) {
				draw(manifest);
				current_manifest = manifest;
			}
		}
		catch (e) {
			console.log(e);

			var message = e.problem;
			if (e.context) { message += e.context; }
			addErrorMessage(e.problemMark.line, e.problemMark.column, message);
		}
	}

	var setUpDisplay = function() {
		//$("#pm_manifest_yaml_block").css(textarea.styles);
		for (var styleName in textarea.styles) {
			$("#pm_manifest_yaml_block").css(styleName, textarea.styles[styleName] + "px");
		}
	}

	setUpDisplay();

	if ($("#pm_manifest_yaml_block").val() != '') {
		renderYAML();
	}

	$("#pm_manifest_yaml_block").on("keyup", renderYAML);

	$.getJSON(
		'/configuration/plugins?format=json',
		null,
		function(response) {
			plugins = response.data.plugins;

			$('.pm-bare-plugin-name').each(function(i, el) {
				var this_plugin = plugins[el.textContent];

				$(el).replaceWith(
				    "<select>"
				    + "<option value=\"" + this_plugin.name + "\">" + this_plugin.title + " (" + this_plugin.name + ")</option>"
				    + "</select>"
	            );
			});
		}
	);
});
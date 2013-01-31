/**
 * Paasmaker
 *
 * Application manifest editor
 */

//----------------------------------------

var manifest = {};

manifest.manifest = function() {};
manifest.manifest.prototype.format = 1;
manifest.manifest.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item\">"
		+ "<h3>manifest</h3>"
		+ "<p>format: 1</p>"
		+ "</div>"
	);
};

manifest.application = function() {};
manifest.application.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item\">"
		+ "<h3>manifest</h3>"
		+ "<p>format: 1</p>"
		+ "</div>"
	);
};

manifest.instances = function() {};
manifest.instances.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item pm-manifest-instance-list\"></div>"
	);
};

manifest.instance = function() {};
manifest.instance.prototype.name = "";
manifest.instance.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item pm-manifest-instance\">"
		+ "<h3>instance: " + this.name + "</h3>"
		+ "</div>"
	);
};

manifest.services = function() {};
manifest.services.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item pm-manifest-service-list\"></div>"
	);
};

manifest.service = function() {};
manifest.service.prototype.name = "";
manifest.service.prototype.draw = function(container) {
	$(container).append(
		"<div class=\"pm-manifest-item pm-manifest-service\">"
		+ "<h3>service: " + this.name + "</h3>"
		+ "</div>"
	);
};

//----------------------------------------
// http://stackoverflow.com/a/6713782

Object.equals = function( x, y ) {
  if ( x === y ) return true;
    // if both x and y are null or undefined and exactly the same

  if ( ! ( x instanceof Object ) || ! ( y instanceof Object ) ) return false;
    // if they are not strictly equal, they both need to be Objects

  if ( x.constructor !== y.constructor ) return false;
    // they must have the exact same prototype chain, the closest we can do is
    // test there constructor.

  for ( var p in x ) {
    if ( ! x.hasOwnProperty( p ) ) continue;
      // other properties were tested using x.constructor === y.constructor

    if ( ! y.hasOwnProperty( p ) ) return false;
      // allows to compare x[ p ] and y[ p ] when set to undefined

    if ( x[ p ] === y[ p ] ) continue;
      // if they have the same strict value or identity then they are equal

    if ( typeof( x[ p ] ) !== "object" ) return false;
      // Numbers, Strings, Functions, Booleans must be strictly equal

    if ( ! Object.equals( x[ p ],  y[ p ] ) ) return false;
      // Objects and Arrays must be tested recursively
  }

  for ( p in y ) {
    if ( y.hasOwnProperty( p ) && ! x.hasOwnProperty( p ) ) return false;
      // allows x[ p ] to be set to undefined
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
		html += "</div>";
		return html;
	},

	instance: function(structure) {
		var html = "<div class=\"pm-manifest-item pm-manifest-instance\">";
		html += "<h3>instance: " + structure.name + "</h3>";
		if (structure.quantity) {	// TODO: is this required?
			html += "<p>quantity: " + structure.quantity + "</p>";
		}
		if (structure.runtime) {
			html += draw_functions.plugin(structure.runtime);
		}
		if (structure.startup) {
			if (typeof structure.startup != 'array') {
				// throw error
			}
			structure.startup.forEach(function(list_item) {
				html += draw_functions.plugin(list_item);
			});
		}
		if (structure.placement) {
			html += draw_functions.plugin(structure.placement);
		}
		html += "</div>";
		return html;
	},

	instances: function(structure) {
		if (typeof structure != 'array') {
			// throw error
		}

		var html = "<div style=\"border:solid 1px red\"><h3>Instances</h3>";
		structure.forEach(function(list_item) {
			html += draw_functions.instance(list_item);
		});
		html += "</div>";
		return html;
	},

	plugin: function(structure) {
		var html = "<div class=\"pm-manifest-item pm-manifest-service\">";
		if (structure.name) {
			html += "<h3>plugin: " + structure.name + "</h3>";
		}
		if (!structure.plugin) {
			// throw error 
		}
		html += "<p>provider: " + structure.plugin + "</p>";
		html += "</div>";
		return html;
	},

	services: function(structure) {
		if (typeof structure != 'array') {
			// throw error
		}

		var html = "<div style=\"border:solid 1px blue\"><h3>Services</h3>";
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

	var last_drawn_manifest;

	var draw = function(structure) {
		console.log("redrawing")
		var html = "";
		for (var key in structure) {
			html += draw_functions[key](structure[key]);
		}
		$("#pm_manifest_rendered").html(html);
	};

	var addErrorMessage = function(line, column, message) {
		var error_block = $('#pm_manifest_yaml_form').append(
			"<div class=\"pm-manifest-error\""
			+ "style=\"top:" + (5 + (line + 1) * textarea.styles.lineHeight) + "px\">"
			+ message
			+ "</div>"
		);
	};

	$("#pm_manifest_yaml_block").on("keyup", function(e, t, o) {

		var edited_yaml = $("#pm_manifest_yaml_block").val();

		$("#pm_manifest_yaml_form .pm-manifest-error").remove();

		try {
			var manifest = jsyaml.load(edited_yaml);

			if (!Object.equals(manifest, last_drawn_manifest)) {
				draw(manifest);
				last_drawn_manifest = manifest;
			}
		}
		catch (e) {
			console.log(e);

			var message = e.problem;
			if (e.context) { message += e.context; }
			addErrorMessage(e.problemMark.line, e.problemMark.column, message);
		}
	});

	var setUpDisplay = function() {
		//$("#pm_manifest_yaml_block").css(textarea.styles);
		for (var styleName in textarea.styles) {
			$("#pm_manifest_yaml_block").css(styleName, textarea.styles[styleName] + "px");
		}
	}

	setUpDisplay();
});
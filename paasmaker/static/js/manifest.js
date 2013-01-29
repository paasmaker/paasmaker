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


$(function() {
	var textarea = {
		styles: {
			fontSize: 13,
			lineHeight: 15
		}
	}

	var addErrorMessage = function(line, column, message) {
		var error_block = $('#pm_manifest_yaml_form').append(
			"<div class=\"pm-manifest-error\""
			+ "style=\"top:" + (5 + (line + 1) * textarea.styles.lineHeight) + "px\">"
			+ message
			+ "</div>"
		);
	};

	$("#pm_manifest_yaml_block").on("keyup", function(e, t, o) {
		//$("#pm_manifest_yaml_block").css(textarea.styles);
		for (var styleName in textarea.styles) {
			$("#pm_manifest_yaml_block").css(styleName, textarea.styles[styleName] + "px");
		}

		var edited_yaml = $("#pm_manifest_yaml_block").val();

		$("#pm_manifest_yaml_form .pm-manifest-error").remove();

		try {
			console.log(jsyaml.load(edited_yaml));
		}
		catch (e) {
			console.log(e);

			var message = e.problem;
			if (e.context) { message += e.context; }
			addErrorMessage(e.problemMark.line, e.problemMark.column, message);
		}
	});



});
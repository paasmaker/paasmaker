/**
 * Paasmaker
 *
 * Application manifest editor
 */

$(function() {
	var textarea = {
		styles: {
			fontSize: 15,
			lineHeight: 19
		}
	}

	var addErrorMessage = function(line, column, message) {
		var error_block = $('#pm_manifest_yaml_form').append("<div class=\"pm-manifest-error\">" + message + "</div>")

		error_block.css('top', (5 + line * textarea.styles.lineHeight) + "px");
	};

	$("#pm_manifest_yaml_block").on("keyup", function(e, t, o) {
		//$("#pm_manifest_yaml_block").css(textarea.styles);
		for (var styleName in textarea.styles) {
			$("#pm_manifest_yaml_block").css(styleName, textarea.styles[styleName] + "px");
		}

		var edited_yaml = $("#pm_manifest_yaml_block").val();

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
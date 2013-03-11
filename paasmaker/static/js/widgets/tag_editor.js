
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.widgets) { pm.widgets = {}; }

pm.widgets.tag_editor = (function() {
	var container;
	var editarea, outputarea;

	var init_fn = function(form, containing_el)
	{
		container = $(containing_el);
		editarea = $('.editor', container);
		outputarea = $('.output', container);

		var addButton = $('<a href="#">Add...</a>');
		addButton.click(function(t) {
			return function(e){
				var newRow = $('<div class="pair"></div>');
				newRow.append($('<input type="text" class="tag" />'));
				newRow.append($('<input type="text" class="value" />'));
				editarea.append(newRow);
				t.addRemoveButtons();

				e.preventDefault();
			};
		}(this));

		container.append(addButton);
		/*var buildButton = $('<a href="#">Build...</a>');
		buildButton.click(function(e){_self.rebuildOutput()});
		this.container.append(buildButton);*/
		this.addRemoveButtons();

		// When the form is submitted, add our inputs.
		$(form).submit(this.rebuildOutput);

		return this;
	};

	init_fn.addRemoveButtons = function() {
		// Find rows without a remove button.
		var rows = $('.pair', editarea).not('.has-remove');
		rows.each(
			function(index, element)
			{
				var el = $(element);
				var removeButton = $('<a href="#">Remove</a>');
				removeButton.click(
					function(e)
					{
						// Remove it from the DOM.
						el.remove();

						e.preventDefault();
					}
				);
				el.addClass('has-remove');
				el.append(removeButton);
			}
		);
	};

	init_fn.rebuildOutput = function() {
		var rows = $('.pair', editarea);
		outputarea.empty();

		rows.each(function(index, element) {
				var el = $(element);
				var tag = $('.tag', el).val();
				var value = $('.value', el).val();

				var tagEl = $('<input type="hidden" />');
				tagEl.attr({name: 'tags.' + tag, value: value});

				outputarea.append(tagEl);
			}
		);
	};

	return function() {
		return init_fn.apply(init_fn, arguments);
	}
}());

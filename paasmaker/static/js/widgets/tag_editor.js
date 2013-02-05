
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.widgets) { pm.widgets = {}; }

pm.widgets.tag_editor = function(form, container)
{
	this.form = form;
	this.container = container;
	this.editarea = $('.editor', container);
	this.outputarea = $('.output', container);

	var _self = this;
	var addButton = $('<a href="#">Add...</a>');
	addButton.click(
		function(e)
		{
			var newRow = $('<div class="pair"></div>');
			newRow.append($('<input type="text" class="tag" />'));
			newRow.append($('<input type="text" class="value" />'));
			_self.editarea.append(newRow);
			_self.addRemoveButtons();

			e.preventDefault();
		}
	);

	this.container.append(addButton);
	/*var buildButton = $('<a href="#">Build...</a>');
	buildButton.click(function(e){_self.rebuildOutput()});
	this.container.append(buildButton);*/
	this.addRemoveButtons();

	// When the form is submitted, add our inputs.
	$(form).submit(
		function(e)
		{
			_self.rebuildOutput()
		}
	);
}

pm.widgets.tag_editor.prototype.addRemoveButtons = function()
{
	// Find rows without a remove button.
	var rows = $('.pair', this.editarea).not('.has-remove');
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
}

pm.widgets.tag_editor.prototype.rebuildOutput = function()
{
	var rows = $('.pair', this.editarea);
	this.outputarea.empty();
	var _self = this;
	rows.each(
		function(index, element)
		{
			var el = $(element);
			var tag = $('.tag', el).val();
			var value = $('.value', el).val();

			var tagEl = $('<input type="hidden" />');
			tagEl.attr({name: 'tags.' + tag, value: value});

			_self.outputarea.append(tagEl);
		}
	);
}

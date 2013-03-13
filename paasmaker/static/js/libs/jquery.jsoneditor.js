// Simple yet flexible JSON editor plugin; turns any element into a stylable interactive JSON editor.
//
// Original version by David Durman: http://www.daviddurman.com/jquery-json-editor-plugin.html
//
// Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
//
// Requires jQuery, and (optional) the json2 library for older browsers without native JSON parsing.
//
// Example:
//     var myjson = { any: { json: { value: 1 } } };
//     var opt = { change: function() { console.log('value was changed!'); } };
//     $('#mydiv').jsonEditor(myjson, opt);

(function( $ ) {
    var options, current_object;

    /**
     * Attach jsonEditor as a plugin to jQuery. Usage:
     * $(container_element_for_editor).jsonEditor(json_input[, options]);
     *
     * @param json_input JSON-encoded string or pre-parsed object containing
     *                   the data to be displayed in the editor
     * @param options Object containing any of the following options:
     *
     * Event handlers
     * change: function to call whenever a property name or value changes
     * drawproperty: function to call when generating HTML for each property (for custom styles, etc.)
     * valueField: DOM element whose value should be updated whenever a property changes
     *
     * HTML output
     * propertyElement: HTML element to use for key names (defaults to "<input>")
     * valueElement: HTML element to use for values (defaults to "<input>")
     * groupElement: HTML element to enclose groups in (hash/array) of values (defaults to "<span>")
     * buttonElement: HTML element to use for "add item" buttons (defaults to "<button>")
     *
     * Property names
     * newSingleKey: base name to use when creating a new item (defaults to NewKey)
     * newGroupKey: base name to use when creating a new sub-object (defaults to NewGroupKey)
     */
    $.fn.jsonEditor = function(json_input, constructor_opts) {
        var opts = constructor_opts || {};

        var K = function() {};
        if (!opts.change) { opts.change = K; }
        if (!opts.drawproperty) { opts.drawproperty = K; }

        // http://stackoverflow.com/a/1043667
        if (this.length > 1){
            return this.each(function() {
                $(this).jsonEditor(json_input, constructor_opts)
            });
        } else {
            return JSONEditor($(this), json_input, opts);
        }
    };

    /**
     * Constructor and entry point: sets main event handler and triggers initial redraw
     */
    function JSONEditor(target, json_input, opts) {
        options = opts || {};
        options.target_el = target;

        if (typeof json_input == 'string') {
            setJSON(json_input);
        } else {
            setObject(json_input);
        }

        $('.property, .value', options.target_el).live('blur focus', function() {
            $(this).toggleClass('editing');
        });

        $.extend(this, {
            getObject: getObject,
            getJSON: getJSON,
            setObject: setObject,
            setJSON: setJSON,
        });

        return this;
    }

    /**
     * Getters and setters for the current editing object,
     * both as an object or as a JSON-encoded string
     */
    function getJSON() { return JSON.stringify(current_object); }
    function getObject() { return current_object; }
    function setJSON(new_json) { setObject(JSON.parse(new_json)); }
    function setObject(new_object) {
        if (new_object !== null) {
            current_object = new_object;
            redraw();
        }
    }

    /**
     * Quick type identification, for use when drawing the editor.
     */
    function isObject(o) { return Object.prototype.toString.call(o) == '[object Object]'; }
    function isArray(o) { return Object.prototype.toString.call(o) == '[object Array]'; }
    function isBoolean(o) { return Object.prototype.toString.call(o) == '[object Boolean]'; }
    function isNumber(o) { return Object.prototype.toString.call(o) == '[object Number]'; }
    function isString(o) { return Object.prototype.toString.call(o) == '[object String]'; }

    /**
     * Modify the value given by path in object o to new value given by value. If path
     * doesn't exist already, creates a new property within o. Returns the modified object.
     * Example:
     *   changeValue({}, 'foo.bar.baz', 10); // returns { foo: { bar: { baz: 10 } } }
     *
     * @param o object to modify
     * @param path dot-separated list of key names leading
     *             to the property we want to change
     * @param value new value for that property
     */
    function changeValue(o, path, value) {
        var del = (arguments.length == 2);

        if (path.indexOf('.') > -1) {
            var diver = o,
                i = 0,
                parts = path.split('.');
            for (var len = parts.length; i < len - 1; i++) {
                diver = diver[parts[i]];
            }
            if (del) delete diver[parts[len - 1]];
            else diver[parts[len - 1]] = value;
        } else {
            if (del) delete o[path];
            else o[path] = value;
        }
        return o;
    }

    /**
     * In object o, find the property given in path and then rename it
     * to new_key. If new_key is empty, just delete the property.
     * Returns the modified object.
     *
     * @param o object to modify
     * @param path dot-separated list of key names leading
     *             to the property we want to change
     * @param new_key new key name for that property
     */
    function renameProperty(o, path, new_key) {
        if (path.indexOf('.') > -1) {
            var diver = o,
                i = 0,
                parts = path.split('.');
            for (var len = parts.length; i < len - 1; i++) {
                diver = diver[parts[i]];
            }
            diver[new_key] = diver[parts[len - 1]];
            delete diver[parts[len - 1]];
        } else {
            if (new_key) {
                o[new_key] = o[path];
            }
            delete o[path];
        }
        return o;
    }

    /**
     * Get a property by path from object o if it exists. If not, return defaultValue.
     * Example:
     * def({ foo: { bar: 5 } }, 'foo.bar', 100); // returns 5
     * def({ foo: { bar: 5 } }, 'foo.baz', 100); // returns 100
     */
    function def(o, path, defaultValue) {
        path = path.split('.');
        var i = 0;
        while (i < path.length) {
            if ((o = o[path[i++]]) == undefined) return defaultValue;
        }
        return o;
    }

    /**
     * Adds an item with key key_base, value new_value into current_object at path. If an
     * item named key_base already exists at path, add a numeric suffix to make it unique.
     * After adding, redraw the editor and ensure the new item is visible.
     */
    function addNewItem(key_base, path, new_value) {
        var new_key = key_base, suffix = 0;

        var json_at_path = def(current_object, path);
        while (typeof json_at_path[new_key] !== 'undefined') {
            suffix ++;
            new_key = key_base + suffix;
        }
        var new_path = (path ? path + '.' : '') + new_key;

        changeValue(current_object, new_path, new_value);

        redraw();
        itemChange(new_path);
        expand(path);
    }

    /**
     * Expands the view for the child object given by path.
     */
    function expand(path) {
        path_bits = path.match(/(.+)\.([^\.]+)/);
        if (path_bits && path_bits[1] && path_bits[2]) {
            $("div"
                + "[data-path=\"" + path_bits[1] + "\"]"
                + "[data-key=\"" + path_bits[2] + "\"]",
                options.target_el
            ).addClass('expanded');
        }
    }

    /**
     * Externally-focussed event handler for whenever a property or value changes:
     * if a change function was provided, run that, and if an input field to keep
     * updated was provided, update that.
     */
    function itemChange(changed_path) {
        options.change.apply(this, [current_object, changed_path]);

        if (options.valueField) {
            $(options.valueField).val(this.getJSON());
        }
    }

    /**
     * Event handler for clicks on the header of an object or array: distinguish
     * between the expander link, new item button, and new child object button
     */
    function groupClickHandler(e, path) {
        e.preventDefault();
        e.stopPropagation();
        var t = $(e.target);

        if (t.hasClass('expander')) {
            t.parent().toggleClass('expanded');
        }
        if (t.hasClass('add-property')) {
            addNewItem(
                (options.newSingleKey || 'NewKey'),
                path, ''
            );
        }
        if (t.hasClass('add-group')) {
            addNewItem(
                (options.newGroupKey || 'NewGroupKey'),
                path, {}
            );
        }
    }

    /**
     * Event handler for the onchange event of an input field for a property name
     */
    function propertyChangeHandler(e) {
        var path = $(e.target).parent().data('path'),
            val = $(e.target).next().val(),
            newKey = $(e.target).val(),
            oldKey = $(e.target).attr('title');

        renameProperty(current_object, (path ? path + '.' : '') + oldKey, newKey);

        redraw();
        itemChange((path ? path + '.' : '') + newKey);
    }

    /**
     * Event handler for the onchange event of an input field for a value
     */
    function valueChangeHandler(e) {
        var key = $(e.target).prev().val(),
            item = $(e.target).parent(),
            path = item.data('path'),
            val = $(e.target).val() || 'null',
            path_to_change = (path ? path + '.' : '') + key;

        changeValue(current_object, path_to_change, val);

        redraw();
        itemChange(path_to_change);
    }

    /**
     * Detect the type of val and add a corresponding class to item;
     * called during construct() so the form can be styled.
     */
    function assignType(item, val) {
        var className = 'null';

        if (isObject(val)) className = 'object';
        else if (isArray(val)) className = 'array';
        else if (isBoolean(val)) className = 'boolean';
        else if (isString(val)) className = 'string';
        else if (isNumber(val)) className = 'number';

        item.removeClass('object array boolean string number null');
        item.addClass(className);
    }

    /**
     * Add an +/- expander link to item, of class customClass (or "expander"),
     * where item is a <div> element representing a child object or array.
     */
    function addExpander(item, customClass) {
        if (item.children('.expander').length == 0) {
            var expander =   $('<span>',  { 'class': (customClass || 'expander') });
            item.prepend(expander);
        }
    }

    /**
     * Draw a JSON editor form inside root_el for the object given in structure.
     * (Can be called recursively to draw child objects/arrays, given by path.)
     *
     * @param structure object for which we're creating a visual representation
     * @param root_el jQuery-enhanced DOM object
     * @param path dot-separated string giving the location of structure in the overall object
     */
    function construct(structure, root_el, path) {
        path = path || '';

        root_el.children('.item').remove();

        var json_keys = Object.keys(structure);
        json_keys.sort();

        $.each(json_keys, function(i, key) {
            var elements = {};
            elements.item = $('<div>', { 'class': 'item', 'data-path': path, 'data-key': key });

            elements.property = $(options.propertyElement || '<input>', { 'class': 'property' });
            elements.property.val(key).attr('title', key);
            elements.property.change(propertyChangeHandler);

            if (isObject(structure[key]) || isArray(structure[key])) {
                // for objects and arrays, draw a title row (rather than the JSON-encoded value)
                // containing an item count and buttons to add new items
                var count = Object.keys(structure[key]).length;
                count += (count == 1 ? ' item' : ' items');

                addExpander(elements.item);

                elements.value = $(options.groupElement || '<span>', { 'class': 'value-group' });
                elements.value.append(
                    '<span class="value-group-count">' + count + '</span>',
                    $(options.buttonElement || '<button class="add-property">Add item</button>'),
                    $(options.buttonElement || '<button class="add-group">Add group</button>')
                );
            } else {
                // for all other values, just show an input field with the value in the right column
                elements.value = $(options.valueElement || '<input>', { 'class': 'value', 'value': structure[key], 'title': structure[key] });
                elements.value.change(valueChangeHandler);
            }

            // if we were given a handler for the draw property event, run it
            // and see if we need to replace any of the generated elements
            var altered_children = options.drawproperty.apply(this, [options, structure, root_el, path, key]);
            if (altered_children) {
                for (var child_name in altered_children) {
                    elements[child_name] = altered_children[child_name];
                }
            }

            if (isObject(structure[key]) || isArray(structure[key])) {
                // for objects and arrays, set a general click handler for buttons on the title row
                // (do this after running any drawproperty() plugins to ensure event isn't cleared)
                elements.item.bind('click', function(e) {
                    groupClickHandler(e, (path ? path + '.' : '') + key, options);
                });
            }

            elements.item.append(elements.property, elements.value);
            root_el.append(elements.item);

            assignType(elements.item, structure[key]);

            if (isObject(structure[key]) || isArray(structure[key])) {
                construct(structure[key], elements.item, (path ? path + '.' : '') + key);
            }
        });
    }

    /**
     * Detect which child views have been opened, save their details, redraw
     * the form, and then reopen those views. For use whenever an edit occurs.
     */
    function redraw() {
        var expanded_items = [];
        $('.expanded', options.target_el).each(function(i, el) {
            expanded_items.push([$(el).data('path'), $(el).data('key')]);
        });

        construct(current_object, options.target_el);

        $.each(expanded_items, function(i, item) {
            $("div"
                + "[data-path=\"" + item[0] + "\"]"
                + "[data-key=\"" + item[1] + "\"]",
                options.target_el
            ).addClass('expanded');
        });
    }

})( jQuery );

// https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Object/keys
if (!Object.keys) {
  Object.keys = (function () {
    var hasOwnProperty = Object.prototype.hasOwnProperty,
        hasDontEnumBug = !({toString: null}).propertyIsEnumerable('toString'),
        dontEnums = [
          'toString',
          'toLocaleString',
          'valueOf',
          'hasOwnProperty',
          'isPrototypeOf',
          'propertyIsEnumerable',
          'constructor'
        ],
        dontEnumsLength = dontEnums.length;

    return function (obj) {
      if (typeof obj !== 'object' && typeof obj !== 'function' || obj === null) throw new TypeError('Object.keys called on non-object');

      var result = [];

      for (var prop in obj) {
        if (hasOwnProperty.call(obj, prop)) result.push(prop);
      }

      if (hasDontEnumBug) {
        for (var i=0; i < dontEnumsLength; i++) {
          if (hasOwnProperty.call(obj, dontEnums[i])) result.push(dontEnums[i]);
        }
      }
      return result;
    }
  })()
}

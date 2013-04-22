
define([
	'jquery',
	'underscore',
	'backbone',
	'context',
], function($, _, Backbone, Context) {
	var module = {};

	module.initialize = function(myname, resourcePath, callback) {
		require(['tpl!' + resourcePath + 'template.html'], function(template) {
			console.log("Got template");
			console.log(template);
			callback();
		});
	};

	module.SERVICE_EXPORT = function() {
	};

	return module;
});
require.config({
	paths: {
		jquery: 'libs/jquery/jquery',
		underscore: 'libs/underscore/underscore',
		backbone: 'libs/backbone/backbone',
		// WARNING: If you update these paths, make sure to do the same in build.js.
		// Otherwise the compiled version will break.

		// Twitter Bootstrap loading:
		// https://github.com/twitter/bootstrap/pull/534#issuecomment-6438820
		'jquery.bootstrap': 'libs/bootstrap/bootstrap',
		'flot.pie': 'libs/flot/flot.pie',
		'flot': 'libs/flot/flot',
		'jsoneditor': 'libs/jsoneditor/jsoneditor',
		moment: 'libs/moment/moment',
		socketio: 'libs/socket.io/socket.io',
		resumable: 'libs/resumable/resumable',

		// Plugin loading.
		plugin: '/plugin'
	},
	shim: {
		'jquery.bootstrap': {
			deps: ['jquery'],
			exports: 'jquery'
		},
		'flot': {
			deps: ['jquery'],
			exports: 'jquery'
		},
		'flot.pie': {
			deps: ['flot'],
			exports: 'jquery'
		},
		'jsoneditor': {
			deps: ['jquery'],
			exports: 'jquery'
		},
		socketio: {
			exports: 'io'
		},
		resumable: {
			exports: 'Resumable'
		}
	}
});

require([
	'jquery',
	'jquery.bootstrap',
	'flot',
	'flot.pie',
	'jsoneditor',
	'app'
], function($, bootstrap, flot, flotpie, jsoneditor, App) {
	App.initialize();
});
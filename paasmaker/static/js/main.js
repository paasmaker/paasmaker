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
		moment: 'libs/moment/moment',
		socketio: 'libs/socket.io/socket.io',

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
		socketio: {
			exports: 'io'
		}
	}
});

require([
	'jquery',
	'jquery.bootstrap',
	'flot',
	'flot.pie',
	'app'
], function($, bootstrap, flot, flotpie, App) {
	App.initialize();
});
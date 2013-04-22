require.config({
	paths: {
		jquery: 'libs/jquery/jquery',
		underscore: 'libs/underscore/underscore',
		backbone: 'libs/backbone/backbone',
		// Twitter Bootstrap loading:
		// https://github.com/twitter/bootstrap/pull/534#issuecomment-6438820
		'jquery.bootstrap': 'libs/bootstrap/bootstrap',
		// Plugin loading.
		plugin: '/plugin'
	},
	shim: {
		'jquery.bootstrap': {
			deps: ['jquery'],
			exports: 'jquery'
		}
	}
});

require([
	'jquery',
	'jquery.bootstrap',
	'app'
], function($, bootstrap, App) {
	App.initialize();
});
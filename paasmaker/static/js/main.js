require.config({
	paths: {
		jquery: 'libs/jquery/jquery',
		underscore: 'libs/underscore/underscore',
		backbone: 'libs/backbone/backbone',
		// Twitter Bootstrap loading:
		// https://github.com/twitter/bootstrap/pull/534#issuecomment-6438820
		'jquery.bootstrap': 'libs/bootstrap/bootstrap',
		'jquery.flot.pie': 'libs/flot/flot.pie',
		'jquery.flot': 'libs/flot/flot',
		moment: 'libs/moment/moment',
		// Plugin loading.
		plugin: '/plugin'
	},
	shim: {
		'jquery.bootstrap': {
			deps: ['jquery'],
			exports: 'jquery'
		},
		'jquery.flot': {
			deps: ['jquery'],
			exports: 'jquery'
		},
		'jquery.flot.pie': {
			deps: ['jquery.flot'],
			exports: 'jquery'
		}
	}
});

require([
	'jquery',
	'jquery.bootstrap',
	'jquery.flot',
	'jquery.flot.pie',
	'app'
], function($, bootstrap, flot, flotpie, App) {
	App.initialize();
});
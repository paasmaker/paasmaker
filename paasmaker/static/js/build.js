({
    baseUrl: ".",
    paths: {
		jquery: 'libs/jquery/jquery',
		underscore: 'libs/underscore/underscore',
		backbone: 'libs/backbone/backbone',
		// Twitter Bootstrap loading:
		// https://github.com/twitter/bootstrap/pull/534#issuecomment-6438820
		'jquery.bootstrap': 'libs/bootstrap/bootstrap',
		'flot.pie': 'libs/flot/flot.pie',
		'flot': 'libs/flot/flot',
		moment: 'libs/moment/moment',
	},
    name: "main",
    out: "main-built.js"
})
<?php
	// *******************************************
	// *** Database configuration (important!) ***
	// *******************************************

	require(dirname(__FILE__) . '/PmInterface.php');

	$interface = new \Paasmaker\PmInterface(array('../my-project.yml'), TRUE);
	$service = $interface->getService('rsssql');

	define('DB_TYPE', 'mysql');
	// For mysql:
	define('DB_HOST', $service['hostname'] . ':' . $service['port']);
	// For pgsql:
	//define('DB_HOST', $service['hostname']);
	define('DB_RAW_HOST', $service['hostname']);
	define('DB_USER', $service['username']);
	define('DB_NAME', $service['database']);
	define('DB_PASS', $service['password']);
	define('DB_PORT', $service['port']);
	// tt-rss only needs DB_PORT for Postgres,
	// but the schema loader needs it for Postgres.

	define('MYSQL_CHARSET', 'UTF8');
	// Connection charset for MySQL. If you have a legacy database and/or experience
	// garbage unicode characters with this option, try setting it to a blank string.

	// ***********************************
	// *** Basic settings (important!) ***
	// ***********************************

	if (array_key_exists('HTTP_HOST', $_SERVER)) {
		define('SELF_URL_PATH', 'http://' . $_SERVER['HTTP_HOST'] . '/');
	} else {
		define('SELF_URL_PATH', 'http://localhost/');
	}
	// Full URL of your tt-rss installation. This should be set to the
	// location of tt-rss directory, e.g. http://yourserver/tt-rss/
	// You need to set this option correctly otherwise several features
	// including PUSH, bookmarklets and browser integration will not work properly.

// The remainder of the file follows; it is omitted here for brevity.
<?php

if (php_sapi_name() != "cli") {
	echo "You can't run this from the web browser.";
	exit();
}

set_include_path(dirname(__FILE__) ."/include" . PATH_SEPARATOR .
	get_include_path());

require_once "autoload.php";
require_once "functions.php";
require_once "db.php";

// TODO: This doesn't detect between if the schema is loaded or
// if it can't connect to the database.
$result = db_query("SELECT true FROM ttrss_feeds", false);

if ($result) {
	// In this case, there is already tables in the database.
	echo "No database loading required at this time.\n";
} else {
	// There are no tables. Do the first time insert.
	$command = "";
	$path_to_schema = dirname(__FILE__) . '/schema/ttrss_schema_' . DB_TYPE . '.sql';
	if (DB_TYPE == 'mysql') {
		// TODO: This puts the password on the command line.
		$command = "cat " . escapeshellarg($path_to_schema) . " | " .
			"mysql -u " . escapeshellarg(DB_USER) .
			" -h " . escapeshellarg(DB_RAW_HOST) .
			" --port=" . escapeshellarg(DB_PORT) .
			" -p" . escapeshellarg(DB_PASS) . // No space - MySQL doesn't like that.
			" " . escapeshellarg(DB_NAME);

		$code = 0;
		echo "Importing MySQL database...";
		passthru($command, $code);
		exit($code);
	} else {
		$pwfile = tempnam('/tmp', 'ttrss');
		file_put_contents(
			$pwfile,
			DB_RAW_HOST . ':' . DB_PORT . ':' . DB_NAME . ':' . DB_USER . ':' . DB_PASS
		);
		$command = "cat " . escapeshellarg($path_to_schema) . " | " .
			"PGPASSFILE=" . escapeshellarg($pwfile) . " " .
			"psql -U " . escapeshellarg(DB_USER) .
			" -h " . escapeshellarg(DB_HOST) .
			" -p " . escapeshellarg(DB_PORT) .
			" -w " . // Don't ask for password.
			" " . escapeshellarg(DB_NAME);

		$code = 0;
		echo "Importing Postgres database...";
		passthru($command, $code);
		unlink($pwfile);
		exit($code);
	}
}

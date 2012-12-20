<pre>
<?

foreach( $_SERVER as $key => $value )
{
	echo htmlspecialchars($key), " => ";
	if( strlen($value) > 0 and $value[0] == '{' )
	{
		// Assume it's JSON, and decode and print.
		$decoded = json_decode($value, TRUE);
		print_r($decoded);
	}
	else
	{
		echo htmlspecialchars($value), "\n";
	}
}

?>
</pre>

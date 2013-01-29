Wordpress on Paasmaker
======================

It is quite easy to run Wordpress on Paasmaker. It's just standard PHP, without
a special framework.

.. WARNING::
	By default Wordpress will write uploaded images to the filesystem of the server
	that it's on. Paasmaker is designed to run seperate instances of the code that
	don't store persistent files to the filesystem.

	This guide covers how to use Amazon S3 to store the uploaded images. If you do
	not follow this guide and use Amazon S3, or do not use another method to preserve
	the files that get uploaded, you may lose data.

Getting Started
---------------

For this guide, we're assuming that:

* You have a local installation of Paasmaker for development, that's configured
  with the development mode plugin.
* Your local installation of Paasmaker has the PHP runtime enabled and configured.
* You are using some kind of source control to manage your code. In this example,
  we use Git to manage this.

Create the git repository
-------------------------

Use your normal tools to create a git repository, and hook it up to the remote repository.

For example, with BitBucket, you would do the following::

	mkdir paasmaker-wordpress
	cd paasmaker-wordpress
	git init .
	git remote add origin ssh://git@bitbucket.org/freefoote/paasmaker-wordpress-sample.git
	... make your changes ...
	git commit
	git push -u origin master

Download Wordpress and set up on Paasmaker
------------------------------------------

Download the latest version of Wordpress, and unpack it into your repository root.

Before you do anything else, check in all the files, so you have a pristine copy of
Wordpress, and you can easily see what you've changed since you downloaded it.

At time of writing, we used version 3.5.1.

For example::

	wget http://wordpress.org/latest.tar.gz
	tar -zxvf latest.tar.gz
	rm latest.tar.gz
	git add .
	git commit

Now, before we go any further, we need to add a manifest file. Create ``manifest.yml``
in the root of the repository, with the following contents::

	manifest:
	  format: 1

	application:
	  name: paasmaker-example-wordpress
	  prepare:
	    runtime:
	      name: paasmaker.runtime.php
	      version: 5.3

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      name: paasmaker.runtime.php
	      version: 5.3
	      parameters:
	        document_root: wordpress
	    placement:
	      strategy: paasmaker.placement.default

	services:
	  - name: paasmaker-example-wordpress
	    provider: paasmaker.service.mysql

At this stage, you can add your application to Paasmaker, using the development directory
SCM plugin. Find out the directory that you've put the files in, and enter that directory.
Note that you should put the directory that has the ``manifest.yml`` file in it. You can
register and then start the instance. At this stage, it won't work, and you **should not**
do the installation via the web interface yet.

Download the latest version of the Paasmaker PHP interface from `the repository on BitBucket
<https://bitbucket.org/freefoote/paasmaker-interface-php/src>`_ - you're looking for
``PmInterface.php``. Put it into the ``wordpress/`` directory in your project.

Copy the ``wordpress/wp-config-sample.php`` file into ``wordpress/wp-config.php``, and then
make a few changes to the file.::

	<?php
	/**
	 * The base configurations of the WordPress.
	 *
	 * This file has the following configurations: MySQL settings, Table Prefix,
	 * Secret Keys, WordPress Language, and ABSPATH. You can find more information
	 * by visiting {@link http://codex.wordpress.org/Editing_wp-config.php Editing
	 * wp-config.php} Codex page. You can get the MySQL settings from your web host.
	 *
	 * This file is used by the wp-config.php creation script during the
	 * installation. You don't have to use the web site, you can just copy this file
	 * to "wp-config.php" and fill in the values.
	 *
	 * @package WordPress
	 */

	// Your version of Wordpress won't be listening on port 80 or 443,
	// so this convinces it otherwise.
	define('WP_SITEURL', "http://" . $_SERVER['HTTP_X_FORWARDED_HOST'] . ':' . $_SERVER['HTTP_X_FORWARDED_PORT']);

	require('PmInterface.php');

	$interface = new \Paasmaker\PmInterface(array());

	// This service name matches what you put in your manfiest file.
	$databaseService = $interface->getService('paasmaker-example-wordpress');

	// ** MySQL settings - You can get this info from your web host ** //
	/** The name of the database for WordPress */
	define('DB_NAME', $databaseService['database']);

	/** MySQL database username */
	define('DB_USER', $databaseService['username']);

	/** MySQL database password */
	define('DB_PASSWORD', $databaseService['password']);

	/** MySQL hostname */
	define('DB_HOST', $databaseService['hostname'] . ":" . $databaseService['port']);

	/** Database Charset to use in creating database tables. */
	define('DB_CHARSET', 'utf8');

	/** The Database Collate type. Don't change this if in doubt. */
	define('DB_COLLATE', '');

	/**#@+
	 * Authentication Unique Keys and Salts.
	 *
	 * Change these to different unique phrases!
	 * You can generate these using the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}
	 * You can change these at any point in time to invalidate all existing cookies. This will force all users to have to log in again.
	 *
	 * @since 2.6.0
	 */
	// Paasmaker note: we used the link above (https://api.wordpress.org/secret-key/1.1/salt/) to
	// generate the salt.
	define('AUTH_KEY',         'snip');
	define('SECURE_AUTH_KEY',  'snip');
	define('LOGGED_IN_KEY',    'snip');
	define('NONCE_KEY',        'snip');
	define('AUTH_SALT',        'snip');
	define('SECURE_AUTH_SALT', 'snip');
	define('LOGGED_IN_SALT',   'snip');
	define('NONCE_SALT',       'snip');

	/**#@-*/

	/**
	 * WordPress Database Table prefix.
	 *
	 * You can have multiple installations in one database if you give each a unique
	 * prefix. Only numbers, letters, and underscores please!
	 */
	$table_prefix  = 'wp_';

	/**
	 * WordPress Localized Language, defaults to English.
	 *
	 * Change this to localize WordPress. A corresponding MO file for the chosen
	 * language must be installed to wp-content/languages. For example, install
	 * de_DE.mo to wp-content/languages and set WPLANG to 'de_DE' to enable German
	 * language support.
	 */
	define('WPLANG', '');

	/**
	 * For developers: WordPress debugging mode.
	 *
	 * Change this to true to enable the display of notices during development.
	 * It is strongly recommended that plugin and theme developers use WP_DEBUG
	 * in their development environments.
	 */
	define('WP_DEBUG', false);

	/* That's all, stop editing! Happy blogging. */

	/** Absolute path to the WordPress directory. */
	if ( !defined('ABSPATH') )
		define('ABSPATH', dirname(__FILE__) . '/');

	/** Sets up WordPress vars and included files. */
	require_once(ABSPATH . 'wp-settings.php');

Now that you've done that, you can visit the instance and follow the installation instructions,
selecting a site name and an administrative user. Your Wordpress installation is now working
in development mode.

At this stage, you can check in the updated files, which will be ``wp-config.php``, ``manifest.yml``,
and ``PmInterface.php``. You will also notice a ``paasmaker_env_web.sh`` file, which you should
add to your version control's ignore list - it's not required here.

You will probably also need to workaround an issue where Wordpress will enter a redirect loop
on the public side of the blog. This is an issue with Wordpress being behind proxies (which is
the case with Paasmaker). To work around this, edit the ``wordpress/wp-includes/template-loader.php``
file, and comment out the top block::

	/*if ( defined('WP_USE_THEMES') && WP_USE_THEMES )
		do_action('template_redirect');*/

Using Amazon S3
---------------

Using your development site, use the plugin browser tool to locate the "Amazon S3 for WordPress
with CloudFront 0.4.1.1". Install it on your development site.

Before you configure it, check in all the files that it downloaded for you. You can then configure
the plugin by going to Settings -> Amazon S3.

TODO: This is currently not working. Research and fix this.
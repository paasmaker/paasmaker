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

Create the source tree
----------------------

.. code-block:: bash

	$ mkdir paasmaker-wordpress
	$ cd paasmaker-wordpress
	$ git init .

Download Wordpress and set up on Paasmaker
------------------------------------------

Download the latest version of Wordpress, and unpack it into your repository root.

Before you do anything else, check in all the files, so you have a pristine copy of
Wordpress, and you can easily see what you've changed since you downloaded it.

.. note::
	This isn't the best workflow for tracking remote changes to Wordpress. Please
	let us know if you have suggestions on how to do this in a better way.

At time of writing, we used version 3.5.1.

For example:

.. code-block:: bash

	$ wget http://wordpress.org/latest.tar.gz
	$ tar -zxvf latest.tar.gz
	$ rm latest.tar.gz
	$ git add .
	$ git commit

Now, before we go any further, we need to add a manifest file. Create ``manifest.yml``
in the root of the repository, with the following contents:

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: paasmaker-wordpress
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
	  - name: wordpresssql
	    provider: paasmaker.service.mysql

.. note::
	If you're Ubuntu 12.10 and above, check to see if you have PHP 5.4 instead of 5.3.
	You can run ``php -v`` to check this. If it says 5.4, change 5.3 to 5.4 in the
	manifest file.

Next, download the latest version of the Paasmaker PHP interface from `the repository on BitBucket
<https://bitbucket.org/paasmaker/paasmaker-interface-php/src>`_ - you're looking for
``PmInterface.php``. Put it into the ``wordpress/`` directory in your project.

Copy the ``wordpress/wp-config-sample.php`` file into ``wordpress/wp-config.php``.

.. code-block:: bash

	$ cp wordpress/wp-config-sample.php wordpress/wp-config.php

Then make a few changes to ``wordpress/wp-config.php``. The highlighted lines show the updates.
Don't forget to generate secret salts from `Wordpress's salt generator <https://api.wordpress.org/secret-key/1.1/salt/>`_.

.. literalinclude:: support/paasmaker-wp-config.php
	:language: php
	:emphasize-lines: 17-39,56-65

Your file structure in the repository should now look like this. Note that all the Wordpress
files are in a subdirectory, and that's the public document root. This allows you to check
in files that should not be public, such as the application manifest file.

.. code-block:: none

	.
	+ manifest.yml
	+ wordpress
	  + wp-config.php
	  + PmInterface.php
	  + index.php
	  + ... other wordpress files ...

At this stage, you can add your application to Paasmaker, using the development directory
SCM plugin. Find out the directory that you've put the files in, and enter that directory.
Note that you should put the directory that has the ``manifest.yml`` file in it. You can
register and then start the instance.

Now that you've done that, you can visit the instance and follow the installation instructions,
selecting a site name and an administrative user. Your Wordpress installation is now working
in development mode. At this stage, it'll be writing to the database that Paasmaker created
for you on your local machine.

At this stage, you can check in the updated files, which will be ``wp-config.php``, ``manifest.yml``,
and ``PmInterface.php``. You will also notice a ``paasmaker_env_web.sh`` file, which you should
add to your version control's ignore list - it's not required here.

.. code-block:: bash

	$ echo "/paasmaker_env_web.sh" >> .gitignore
	$ git add .
	$ git commit

Template redirect loop
----------------------

You will probably also need to workaround an issue where Wordpress will enter a redirect loop
on the public side of the blog, redirecting the user's custom template. This is an issue with Wordpress
being behind proxies (which is the case with Paasmaker). To work around this, edit the
``wordpress/wp-includes/template-loader.php`` file, and comment out the top block:

.. code-block:: php

	/*if ( defined('WP_USE_THEMES') && WP_USE_THEMES )
		do_action('template_redirect');*/

Installing plugins
------------------

You should not install plugins on your production version of Wordpress. This is because Wordpress
downloads and writes the files out to the instance directory, which Paasmaker will delete when
the instance is recycled.

Instead, you should install the plugins locally when running Paasmaker in development. This allows
you to track the files that it requires.

For our example, you can go ahead and install plugins if you're using the local SCM directory
mode. Then check in the files once it's installed.

Fixing the hostname issue
-------------------------

A discussion point around Wordpress has always been around relative and absolute URLs used
by Wordpress. We won't get into the discussion other than to show how to work around this
issue so you can host the blog with Paasmaker.

Install the `Root Relative URLs <http://wordpress.org/extend/plugins/root-relative-urls/>`_
plugin via the web console. Then activate it. Once you activate it, initially your Wordpress
will stop working and appear unstyled and without images. This is because the plugin does
not take into account the port number of the incoming request. To fix this, edit one of the
plugin files and comment out a line:

.. code-block:: php

	# In file wordpress/wp-content/plugins/root-relative-urls/sb_root_relative_urls.php
	# Change this, starting at line 72:
	return MP_WP_Root_Relative_URLS::scheme(
	    'http://' . @$_SERVER['HTTP_HOST'] .
	    (!empty($relative) ? '/' . $relative : '') .
	    (isset($url['fragment']) ? '#' . $url['fragment'] : '')
	);

	# To this:
	return MP_WP_Root_Relative_URLS::scheme(
	    // 'http://' . @$_SERVER['HTTP_HOST'] .
	    (!empty($relative) ? '/' . $relative : '') .
	    (isset($url['fragment']) ? '#' . $url['fragment'] : '')
	);

This update removes the hostname from all links on the page that are not required to be
absolute.

TODO: This currently breaks the WP Read Only plugin below.

Using Amazon S3
---------------

Using your development site, use the plugin browser tool to locate the `WP Read Only
<http://wordpress.org/extend/plugins/wpro/>`_ plugin, which automatically uploads images
to S3, and then links them into your posts automatically. It's designed for multi node
scaling systems like Paasmaker.

Once you've installed the plugin, don't forget to check in the files into your repository.

Going into production
---------------------

Add notes here.
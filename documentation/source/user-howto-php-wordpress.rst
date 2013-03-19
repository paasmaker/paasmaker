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

	Additionally, plugins and themes installed directly into a production instance
	will be lost when that instance is recycled. If you follow the workflow suggested
	in the guide, you can avoid this issue.

Getting Started
---------------

For this guide, we're assuming that:

* You have a local installation of Paasmaker for development, that's configured
  with the development mode plugin.
* Your local installation of Paasmaker has the PHP runtime enabled and configured.
* You are using some kind of source control to manage your code. In this example,
  we use Git to manage this.

Download Wordpress and set up on Paasmaker
------------------------------------------

Create a directory, and set it up for git.

.. code-block:: bash

	$ mkdir paasmaker-wordpress
	$ cd paasmaker-wordpress
	$ git init .

Download the latest version of Wordpress, and unpack it into your repository root.

Before you do anything else, check in all the files, so you have a pristine copy of
Wordpress, and you can easily see what you've changed since you downloaded it.

At time of writing, we used version 3.5.1:

.. code-block:: bash

	$ wget http://wordpress.org/latest.tar.gz
	$ tar -zxvf latest.tar.gz
	$ rm latest.tar.gz
	$ git add .
	$ git commit

.. note::
	This isn't the best workflow for tracking remote changes to Wordpress. Please
	let us know if you have suggestions on how to do this in a better way.

Now, before we go any further, we need to add a manifest file. Create ``manifest.yml``
in the root of the repository, with the following contents:

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: paasmaker-wordpress

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.php
	      version: 5.3
	      parameters:
	        document_root: wordpress

	services:
	  - name: wordpresssql
	    plugin: paasmaker.service.mysql

.. note::
	If you're Ubuntu 12.10 and above, check to see if you have PHP 5.4 instead of 5.3.
	You can run ``php -v`` to check this. If it says 5.4, change 5.3 to 5.4 in the
	manifest file.

Next, download the latest version of the Paasmaker PHP interface from `the repository on BitBucket
<https://bitbucket.org/paasmaker/paasmaker-interface-php/src>`_; you're looking for
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
	+ wordpress/
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
add to your version control's ignore list, as it's written out by Paasmaker when it starts your
instance.

.. code-block:: bash

	$ echo "/paasmaker_env_web.sh" >> .gitignore
	$ git add .
	$ git commit

Template redirect loop and the hostname issue
---------------------------------------------

If you try to visit the public side of the blog, you will notice that it enters a redirect loop.
Additionally, Wordpress has a preference for absolute URLs (including the domain name) which
will interfere with moving the blog between development and production.

There isn't an easy way to fix this issue, and we don't intend to enter the debate here.
Our solution is to add some more functions, and patch your template to use them as a filter
for URLs. This solution is not particularly elegant.

In ``wordpress/wp-includes/functions.php``, add the following code to the bottom. This code
is adapted from `this blog post about relative URLs <http://www.deluxeblogtips.com/2012/06/relative-urls.html>`_.

.. code-block:: php

	# In wordpress/wp-includes/functions.php :
	function pm_make_link_relative( $link ) {
	    return preg_replace( '|https?://[^/]+(/.*)|i', '$1', $link );
	}

	function pm_relative_urls() {
	    // Don't do anything if:
	    // - In feed
	    // - In sitemap by WordPress SEO plugin
	    if ( is_feed() || get_query_var( 'sitemap' ) )
	        return;
	    $filters = array(
	        'post_link',
	        'post_type_link',
	        'page_link',
	        'attachment_link',
	        'get_shortlink',
	        'post_type_archive_link',
	        'get_pagenum_link',
	        'get_comments_pagenum_link',
	        'term_link',
	        'search_link',
	        'day_link',
	        'month_link',
	        'year_link',
	        'option_siteurl',
	        'blog_option_siteurl',
	        'option_home',
	        'admin_url',
	        'home_url',
	        'includes_url',
	        'site_url',
	        'plugins_url',
	        'content_url',
	        'site_option_siteurl',
	        'network_home_url',
	        'network_site_url'
	    );
	    foreach ( $filters as $filter )
	    {
	        add_filter( $filter, 'pm_make_link_relative' );
	    }
	}

Then, each template that you use will need an additional filter applied to it.
In our example case, we were using the twentytwelve theme, which required this
additional line:

.. code-block:: php

	# In wordpress/wp-content/themes/twentytwelve/functions.php

	add_action( 'after_setup_theme', 'twentytwelve_setup' );
	# This line is the new line. It should appear after the line above.
	add_action( 'template_redirect', 'pm_relative_urls' );

Each theme should be structured similarly, but you may need to locate the correct
location to insert this code.

This fix has not been tested with multi user blogs.

Installing plugins and themes
-----------------------------

You should not install plugins on your production version of Wordpress. This is because Wordpress
downloads and writes the files out to the instance directory, which Paasmaker will delete when
the instance is recycled.

Instead, you should install the plugins locally when running Paasmaker in development. This allows
you to track the files that it requires with your source control system.

For our example, you can go ahead and install plugins if you're using the local SCM directory
mode. Then check in the files once it's installed.

Using Amazon S3
---------------

Using your development site, use the plugin browser tool to locate the `WP Read Only (WPRO)
<http://wordpress.org/extend/plugins/wpro/>`_ plugin, which automatically uploads images
to S3, and then links them into your posts automatically. It's designed for multi node
scaling systems like Paasmaker.

Once you've installed the plugin, you can activate it and configure it via the settings.
You will need to make sure that the bucket endpoint matches where you created the Amazon
S3 bucket.

Be sure to check in the plugin files once you're happy.

Going into production
---------------------

Assuming that you've checked in all your changes, and hooked up git to a remote URL and
pushed all those changes there, you can then deploy Wordpress on your production infrastructure.

During this, Paasmaker will create a new database for you. When you start up Wordpress
for the first time, it will run through the setup Wizard again. This is then your production
instance and you should treat the content you enter as such.

You will need to activate any plugins that you want again, and reconfigure them. This is
because we're not copying the database from development to production.

To install new plugins, you will need to do this in your development environment, and then
check in the new files. Once you deploy your new revision on Paasmaker, the plugins will
show up in the plugins list and can be activated and configured on live.

The same applies for themes; you will need to install or develop themes in your development
environment, and then check them in and deploy them. This has the added advantage of tracking
your changes with source control.

Changing the sitename
---------------------

During installation, Wordpress recorded the current absolute domain name. In my example,
this ended up being ``http://1.web.paasmaker-wordpress.test.local.paasmaker.net:42530``,
and can't be changed without modifying the database. It would have also set the Site Address
to the same value, but this can be changed. If you go into the Admin area, under Settings > General,
you can enter the correct site URL, which it will use when it needs an absolute link in the live
environment. This is critical to showing the correct URL to users.
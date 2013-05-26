Tiny Tiny RSS Howto
===================

`Tiny Tiny RSS <http://tt-rss.org/>`_ (or tt-rss for short) is a web based
RSS feed reader, written in PHP. It is basically a version of Google reader
that you can run yourself. There are mobile apps available for it if you prefer
to consume your RSS feeds that way.

You can run your own tt-rss installation on top of Paasmaker with a few modifications.

Architecture
------------

TT-RSS has a few different ways to update RSS feeds. The way that fits the easiest
with Paasmaker is to run the update daemon in the background.

So, to set it up, we have two instance types:

1. The web front end, that serves up the website.
2. The fetcher, that is a :term:`standalone instance` (doesn't require a TCP port or routing)
   and is :term:`exclusive <exclusive instance>` (which means only one version will be running
   at a time, and only the current version is active).

Getting started
---------------

Firstly, create yourself a directory, and set it up with your source control
system. Then download the latest tt-rss installation, and check in that pristine
copy. At the time of writing, I used version 1.7.8.

.. code-block:: bash

	$ mkdir my-ttrss
	$ cd my-ttrss
	$ git init .
	$ wget https://github.com/gothfox/Tiny-Tiny-RSS/archive/1.7.9.tar.gz
	$ tar -ztvf 1.7.9.tar.gz
	$ mv Tiny-Tiny-RSS-1.7.9 tt-rss
	$ rm 1.7.9.tar.gz
	$ git add .
	$ git commit

Now, you can add the Paasmaker manifest file, as ``manifest.yml``. Be
sure to replace "your-hostname-here.com" with the actual hostname you'll
use to access it permanently.

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: tt-rss
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - cd tt-rss
	            - for DIR in feed-icons cache cache/export cache/images cache/js cache/simplepie
	            - do
	            -   if [ ! -d $DIR ];
	            -   then
	            -     mkdir $DIR
	            -   fi
	            - done
	            - php schemaloader.php

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.php
	      version: 5.3+
	      parameters:
	        document_root: tt-rss
	    hostnames:
	      - your-hostname-here.com
	  - name: fetcher
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	      parameters:
	        launch_command: php tt-rss/update_daemon2.php
	    exclusive: true
	    standalone: true

	services:
	  - name: rsssql
	    plugin: paasmaker.service.mysql

Configuration and the database
------------------------------

TT-RSS ships with an installer script, which writes out a configuration
file, and loads the initial database schema. With Paasmaker though, you will
need to check in a configuration file, and the configuration will need to
fetch the database access details from Paasmaker itself.

Because the installer isn't run, there would be no database schema either.

So, to get around all of these, firstly grab the Paasmaker PHP interface
main file:

.. code-block:: bash

	$ cd tt-rss
	$ wget https://bitbucket.org/paasmaker/paasmaker-interface-php/raw/ebf5785a972013e9789efa97aef15b3de3f841cf/PmInterface.php

Now, copy the ``tt-rss/config.php-dist`` file to ``tt-rss/config.php``
and make the highlighted changes below. Also skim through the rest of
the file and make any other changes that you need.

.. code-block:: bash

	$ cp config.php-dist config.php

.. literalinclude:: support/tt-rss-config.php
	:language: php
	:emphasize-lines: 6-16,26-30,36

Now add a new script, in ``tt-rss/schemaloader.php`` with the following
contents. This script is called in the prepare phase to load the database
schema.

.. literalinclude:: support/tt-rss-schemaloader.php
	:language: php

.. WARNING::
	The schema loader here currently can't detect between "no schema" and
	"unable to connect to the database". If it is not loading the schema,
	check the prepare logs to make sure it could connect.

File layout
-----------

You will need to edit the ``tt-rss/.gitignore`` that came with TT-RSS to not ignore
the ``config.php`` file.

.. code-block:: bash

	$ vim tt-rss/.gitignore
	... remove config.php ..

At this stage, your root directory should look like this:

.. code-block:: none

	+ my-ttrss
	  + manifest.yml
	  + tt-rss
	    + config.php
	    + schemaloader.php
	    + PmInterface.php
	    + ... other files from tarball

Testing
-------

To test this locally, you can use the development directory SCM to fire up
your local copy. However, when you do this, it won't load the database schema,
because it doesn't run the prepare commands. So, once you have it running,
you'll need to execute the following commands. You'll need to be in the
``tt-rss`` directory to do this:

.. code-block:: bash

	$ cd tt-rss
	$ ../paasmaker_env_web.sh php schemaloader.php

And then it will have the database schema.

The default database username and password is 'admin' and 'password'.

When you log in, TT-RSS will mention that the fetcher isn't running. That's because
the instance type for the fetcher is :term:`exclusive <exclusive instance>`, meaning
that Paasmaker will only run that instance type if it's the current version, and ensure
that the instance type is not running in other versions. So, to start the fetcher, all
you need to do is to make the version the current version, and Paasmaker will start
the fetcher instance type for you.

Complete
--------

Now that you've tested it locally, you can check in all the files:

.. code-block:: bash

	$ git add .
	$ git commit

And deploy to your production Paasmaker cluster.
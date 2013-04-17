
User Manual
===========

This is the users manual, targetted at end users of Paasmaker. End users
means developers writing applications that run on Paasmaker, and users who
will interact with Paasmaker to deploy those applications.

If you are new to Paasmaker, it is suggested that you go through the concepts
below, to understand how Paasmaker works and how it runs your applications.

.. toctree::
   :maxdepth: 2

   user-gettingstarted
   user-concepts
   user-application-manifest
   user-commandline

An important point
------------------

.. WARNING::
	Paasmaker works by having a copy of your code that it deploys
	to servers as it needs to. When a server is done with that code,
	it will delete the files from the server (called deregistration).
	Any data stored on the filesystem next to your code files will be lost.
	Your applications must store data either in a database of some kind,
	or an external filesystem (such as Amazon S3). This is a limitation
	of most PaaS systems and is not unique to Paasmaker.

.. _user-languages-entry:

Integrating with different languages
------------------------------------

Below are some notes on integrating with specific languages.

.. toctree::
   :maxdepth: 2

   user-howto-php
   user-howto-ruby
   user-howto-python
   user-howto-nodejs
   user-howto-generic

Preparing and starting applications
-----------------------------------

Paasmaker ships with a few plugins that are used during the prepare
and startup phase of applications.

.. toctree::
	:maxdepth: 2

	plugin-prepare-shell
	plugin-prepare-pythonpip
	plugin-startup-filesystemlinker

Runtime Plugins
---------------

Depending on your server configuration, you will have a set of runtimes
available. For those runtimes, you can configure them somewhat from your
application. The documentation for each plugin shows how to do that.

.. toctree::
	:maxdepth: 2

	plugin-runtime-shell
	plugin-runtime-php
	plugin-runtime-static
	plugin-runtime-rbenv
	plugin-runtime-nvm

Service Plugins
---------------

Depending on your server configuration, you will have a set of services
available. For those services, you can configure them somewhat from your
application. The documentation for each plugin shows how to do that.

.. toctree::
	:maxdepth: 2

	plugin-service-mysql
	plugin-service-managedmysql
	plugin-service-postgres
	plugin-service-managedpostgres
	plugin-service-managedredis
	plugin-service-s3bucket
	plugin-service-parameters
	plugin-service-filesystem
	plugin-service-managedmongodb
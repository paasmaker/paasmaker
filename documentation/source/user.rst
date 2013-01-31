
User Manual
===========

This is the users manual, targetted at end users of Paasmaker. End users
means developers writing applications that run on Paasmaker, and users who
will interact with Paasmaker to deploy those applications.

If you are new to Paasmaker, it is suggested that you go through the concepts
below, to understand how Paasmaker works and how it runs your applications.

.. toctree::
   :maxdepth: 2

   user-concepts

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

Integrating with different languages
------------------------------------

Below are some notes on integrating with specific languages.

.. toctree::
   :maxdepth: 2

   user-howto-php
   user-howto-ruby
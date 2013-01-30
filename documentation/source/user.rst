
User Manual
===========

This is the users manual, targetted at end users of Paasmaker.

General integration notes
-------------------------

.. WARNING::
	Paasmaker works by having a copy of your code that it deploys
	to servers as it needs to. When a server is done with that code,
	it will delete the files from the server. Any data stored on the
	filesystem next to your code files will be lost. Your applications must
	store data either in a database of some kind, or an external filesystem
	(such as Amazon S3). This is a limitation of most PaaS systems and
	is not unique to Paasmaker.

Integrating with different languages
------------------------------------

.. toctree::
   :maxdepth: 2

   user-howto-php
   user-howto-ruby
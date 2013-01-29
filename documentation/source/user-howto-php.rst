PHP Support
===========

Paasmaker is able to run PHP applications. By default, it will use version 5.3.
The implementation starts up an Apache 2 server per heart node, and all applications
run under that server instance. Each instance is given it's own virtual host for
that application, with a seperate port.

Integrating with common Frameworks and CMSs
-------------------------------------------

The guides below show how to integrate Paasmaker with some common PHP frameworks
and CMS systems, including pitfalls for them.

.. toctree::
   :maxdepth: 2

   user-howto-php-wordpress

Integrating with any PHP project
--------------------------------

If you're using your own PHP framework, or a framework not documented, you should
be able to integrate Paasmaker easily into that system.

TODO: Write this.
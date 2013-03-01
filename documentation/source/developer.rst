

Developers Manual
=================

This is the developers manual, aimed at developers writing plugins or
working on the core of the system.

API
---

Paasmaker ships with a complete set of Python classes to interact with
the server. This API is used by the command line client. You are also
able to use this client directly.

However, if you are not using Python, you'll instead need to write your
own code to interface with Paasmaker. It's not too diffcult and the server
side tries to make this as easy as possible.

.. toctree::
   :maxdepth: 2

   developer-api
   developer-apiauth

Plugins
-------

Paasmaker contains a plugin API for many components, that allow
you to easily extend Paasmaker in specific ways. Plugins allow
you to add new runtimes (languages) and services (for example, databases).

.. toctree::
   :maxdepth: 2

   developer-plugins

Testing
-------

Paasmaker tries to be as tested as it can, to ensure that it works
correctly and that any regressions or errors in future coding are caught.

.. toctree::
   :maxdepth: 2

   developer-testing

Internals
---------

These document the internals of Paasmaker, useful for if you are
hacking the core or developing plugins that require advanced
integration with Paasmaker.

.. toctree::
   :maxdepth: 2

   developer-configuration
   developer-utils
   developer-managed
   developer-model
   developer-router
   developer-controller
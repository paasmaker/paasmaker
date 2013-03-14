File System Linker Startup
==========================

This plugin is designed to work with the :doc:`plugin-service-filesystem`
to link persistent directories into your instance, for legacy applications.

For example, if you have this in your manifest file:

.. code-block:: yaml

	instances:
	  - name: web
	    ...
	    startup:
	      - plugin: paasmaker.startup.filesystemlinker
	        parameters:
	          directories:
	            - web/images

	services:
	  - name: filesystem
	    plugin: paasmaker.service.filesystem

In the example above, it will symlink the directory ``web/images`` in your
code into a persistent location that the filesystem service chose for it.

You can specify several directories to be linked up.

There are a few rules you need to be aware of:

* If the directory already exists in your source code, the contents
  of it are assumed to be authoritive, and are copied over any files
  already in the persistent location. The directory inside your code
  is them removed and symlinked to it's persistent location.
* If the directory doesn't exist in your source code, it is created and
  linked. Any parent directories that don't exist will also be created
  along the way.
* You can not nest linked directories. For example, don't supply both
  ``web/images`` and ``web/images/thumbnails``. The plugin will detect
  if you have done this and abort with an error.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.startup.filesystemlinker.FilesystemLinker
	  name: paasmaker.startup.filesystemlinker
	  title: Filesystem Linker Startup

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.startup.filesystemlinker.FilesystemLinkerParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

This plugin has no server configuration options.
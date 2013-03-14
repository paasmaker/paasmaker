Filesystem Directory Service
============================

This service creates a directory and supplies that path to the applications.
This is currently designed to handle legacy applications that require a
persistent path to write files to. It also only works on a single node,
due to the nature of trying to distribute files reliably across multiple
nodes.

When you request this service in your application:

.. code-block:: yaml

	services:
	  - name: filesystem
	    plugin: paasmaker.service.filesystem

Your application will be supplied a service with credentials like this:

.. code-block:: json

	{
	    "directory": "/full/path/to/directory",
	    "protocol": "directory"
	},

You can use this plugin along with the :doc:`plugin-startup-filesystemlinker` to link persistent
directories into your application codebase.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.filesystem.FilesystemService
	  name: paasmaker.service.filesystem
	  title: Filesystem Service

.. NOTE::
	Where possible, we recommend engineering your application so it doesn't
	write files to the local filesystem, except for caching. We understand some
	legacy systems might not be able to be retrofitted to do this, and thus this
	plugin exists.

.. NOTE::
	It might be possible to allocate directories on a shared NFS filesystem,
	or some other type of clustering filesystem, to make this into a multi-node
	solution. Alternately, depending on your requirements, a solution using
	`lsyncd <https://code.google.com/p/lsyncd/>`_ might be able to work. We will
	leave this one as an excercise for the system administrators.

.. NOTE::
	You will need to find a way to back up the files that applications write into
	this folder.

Application Configuration
-------------------------

This plugin has no application parameters.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.filesystem.FilesystemServiceConfigurationSchema

	The plugin has the following configuration options:
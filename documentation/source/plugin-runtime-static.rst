Static File Runtime
===================

This plugin is designed for serving up static files. It currently
starts up and manages it's own Apache instance, and creates VirtualHosts
on that daemon to serve up the static files.

Apache isn't the fastest server available to serve static files. Instead,
Apache was chosen because it supports ``.htaccess`` files, which then allow
you to do basic redirects, set error documents, or perform access control
operations with the static files.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.static.StaticRuntime
	  name: paasmaker.runtime.static
	  title: Static File Runtime

.. note::
	This plugin is basically a copy of the PHP plugin. In future, we hope
	to provide alternate plugins that are faster at serving static files.

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.runtime.static.StaticRuntimeParametersSchema

	The plugin has the following runtime parameters:

.. note::
	Because this runtime is based on Apache, you can include ``.htaccess`` files
	in your code that can do some redirects, error documents, or other features.
	See the `Apache documentation <http://httpd.apache.org/docs/2.2/>`_ for
	information on how to write ``.htaccess`` files.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.heart.runtime.static.StaticRuntimeOptionsSchema

	The plugin has the following configuration options:
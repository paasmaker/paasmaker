Shell Runtime
=============

This plugin just runs a shell command to start up your application. It
assumes that the application runs in the foreground. Currently, this is how
we support Python applications. In some cases, this is a quick way to support
languages that Paasmaker does not currently have a plugin for.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.shell.ShellRuntime
	  name: paasmaker.runtime.shell
	  title: Shell Runtime

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.runtime.shell.ShellRuntimeParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

This plugin has no server options.
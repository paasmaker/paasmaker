PHP Runtime
===========

This plugin provides PHP support to Paasmaker. It works by starting an
Apache server (one per node) and creating port based VirtualHosts for each
instance that it runs. It uses the system's installed Apache and PHP.

It attempts to use the system's PHP configuration for your application,
including php.ini and any PHP modules configured.

By default, it will start it's own Apache and manage that daemon. It
has the provision to use a system Apache, but this is untested at this time.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.php.PHPRuntime
	  name: paasmaker.runtime.php
	  title: PHP Runtime

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.runtime.php.PHPRuntimeParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

.. colanderdoc:: paasmaker.heart.runtime.php.PHPRuntimeOptionsSchema

	The plugin has the following configuration options:
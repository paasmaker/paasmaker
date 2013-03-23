Nodejs (via nvm) Runtime
========================

This plugin is based on `nvm <https://github.com/creationix/nvm>`_ to provide
multiple versions of Nodejs for running your applications with.

The installer script can install versions of nodejs for you, or you can install them
yourself using nvm's helpers. The plugin will detect any installed versions and
make them available automatically.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.nvm.NvmRuntime
	  name: paasmaker.runtime.node.nvm
	  title: Node (nvm) Runtime

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.runtime.nvm.NvmRuntimeParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

.. colanderdoc:: paasmaker.heart.runtime.nvm.NvmRuntimeOptionsSchema

	The plugin has the following configuration options:

Manual Installation
-------------------

If you don't want to use the installer script, you can manually install nvm
using the instructions from the `github page <https://github.com/creationix/nvm>`_.

If you install it to another location other than ``~/.nvm``, be sure to set that
path when you register the plugin.

Installing additonal Node versions
----------------------------------

The following command relies on having nvm installed and in your path.

List available versions:

.. code-block:: bash

	$ nvm ls-remote

And then install a specific version:

.. code-block:: bash

	$ nvm install v0.9.12

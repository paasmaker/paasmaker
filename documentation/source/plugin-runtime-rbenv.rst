Ruby (via rbenv) Runtime
========================

This plugin is based on `rbenv <https://github.com/sstephenson/rbenv/>`_ to provide
multiple versions of Ruby for running your applications with.

The installer script can install versions of Ruby for you, or you can install them
yourself using rbenv's helpers. The plugin will detect any installed versions and
make them available automatically.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.rbenv.RbenvRuntime
	  name: paasmaker.runtime.ruby.rbenv
	  title: Ruby (rbenv) Runtime

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.heart.runtime.rbenv.RbenvRuntimeParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

.. colanderdoc:: paasmaker.heart.runtime.rbenv.RbenvRuntimeOptionsSchema

	The plugin has the following configuration options:

Manual Installation
-------------------

If you don't want to use the installer script, you can manually install rbenv
using the instructions from the `github page <https://github.com/sstephenson/rbenv/>`_.
Be sure you install the ``ruby-build`` plugin as well.

If you install it to another location other than ``~/.rbenv``, be sure to set that
path when you register the plugin.

Installing additonal Ruby versions
----------------------------------

The following command relies on having rbenv installed and in your path, and having
the ``ruby-build`` plugin installed.

List available versions:

.. code-block:: bash

	$ rbenv install -l

And then install a specific version:

.. code-block:: bash

	$ rbenv install 1.9.3-p327

.. WARNING::
	This will download and install ruby from source. This can take quite a while.

Plugins
=================

Paasmaker is designed to be easily extended in certain manners to offer
additional services or runtimes. The plugins system allows you to offer
these in an easily configurable way, that gives the system administrator
as many options as possible.

Plugin Modes
------------

There are many plugin modes available, each with their own base classes
to keep the API the same. The following documents cover how to write plugins
roughly based on a grouping of what they do.

.. toctree::
   :maxdepth: 2

   developer-plugins-node
   developer-plugins-health

Example Plugin
--------------

.. autoclass:: paasmaker.util.plugin.PluginExample
    :members:

Base Plugin
-----------

All plugins originally descend from the Plugin base class.

.. autoclass:: paasmaker.util.plugin.Plugin
    :members:

Plugin Registry
-----------------

The plugin registry handles instantiating plugins with their
correct runtime options, based on their symbolic name.

.. autoclass:: paasmaker.util.plugin.PluginRegistry
    :members:
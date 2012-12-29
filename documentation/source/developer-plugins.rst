
Plugins
=================

Paasmaker is designed to be easily extended in certain manners to offer
additional services or runtimes. The plugins system allows you to offer
these in an easily configurable way, that gives the system administrator
as many options as possible.

Plugin Modes
------------

The following plugin modes are available inside Paasmaker:

TODO: Complete this list.

SERVICE_CREATE
    This mode is for plugins that can create or update
    application services. It requires runtime parameters
    to operate. Plugins of this sort should be subclasses
    of ``paasmaker.pacemaker.service.base.BaseService``.

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
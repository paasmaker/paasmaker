
Managed Daemons
=================

Originally for testing purposes, the managed daemons are a way to
start, stop, and work with several common external services.

These are designed to start the daemons with a custom configuration
seperate from the system's configuration (with a few exceptions).
They also run under the same user as Paasmaker runs as.

The unit tests use these heavily to test against a brand new instance
of the daemon. The ``ManagedRedis`` class, for instance, is started
and stopped many times during a unit test.

Base Class
----------

.. autoclass:: paasmaker.util.manageddaemon.ManagedDaemon
    :members:

.. autoclass:: paasmaker.util.manageddaemon.ManagedDaemonError
    :members:

Completed Daemons
-----------------

.. autoclass:: paasmaker.util.managedapache.ManagedApache
    :members:

.. autoclass:: paasmaker.util.managednginx.ManagedNginx
    :members:

.. autoclass:: paasmaker.util.postgresdaemon.PostgresDaemon
    :members:

.. autoclass:: paasmaker.util.redisdaemon.RedisDaemon
    :members:

In progress Daemons
-------------------

.. autoclass:: paasmaker.util.managedmysql.ManagedMySQL
    :members:

.. autoclass:: paasmaker.util.managedrabbitmq.ManagedRabbitMQ
    :members:
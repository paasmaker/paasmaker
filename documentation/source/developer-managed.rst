
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

Theory of operation
-------------------

Each managed daemon has a working directory, where the configuration
for that daemon is stored, along with Paasmaker specific metadata,
and also any data files that the daemon uses in normal operation.

Inside the working directory, you will typically see:

* ``service.conf`` - the daemon specific configuration file.
* ``service.json`` - parameters that the daemon was configured with.
  These settings are Paasmaker specific, and will often contain the
  configured port and any other settings.
* A PID file, if the appropriate daemon can be configured to write
  a PID file.
* Any other data files required for the operation of that daemon.
  For example, Redis will contain a ``dump.rdb`` file, whereas
  Postgres will have a series of folders for it's data.

Base Class
----------

.. autoclass:: paasmaker.util.manageddaemon.ManagedDaemon
    :members:

.. autoclass:: paasmaker.util.manageddaemon.ManagedDaemonError
    :members:

Completed Daemons
-----------------

.. autoclass:: paasmaker.util.apachedaemon.ApacheDaemon
    :members:

.. autoclass:: paasmaker.util.nginxdaemon.NginxDaemon
    :members:

.. autoclass:: paasmaker.util.postgresdaemon.PostgresDaemon
    :members:

.. autoclass:: paasmaker.util.redisdaemon.RedisDaemon
    :members:

.. autoclass:: paasmaker.util.mysqldaemon.MySQLDaemon
    :members:

In progress Daemons
-------------------

.. autoclass:: paasmaker.util.managedrabbitmq.ManagedRabbitMQ
    :members:
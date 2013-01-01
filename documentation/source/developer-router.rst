
Routing System
=================

HTTP requests are routed inside the system with several components:

* A NGINX server runs an embedded LUA script.
* The LUA script connects to the router table Redis that stores
  a mapping of hostnames to instance addresses. It also outputs
  a key that allows logging the request to the appropriate version
  type.
* Once the request is complete, NGINX logs the request to a file.
* The access log file is adjusted to write out JSON lines instead
  of the normal plain text.
* Another process comes along and reads the access log file and inserts
  the results into another redis instance.
* Pacemakers update the routing table as instances are started or stopped,
  or errors detected.
* Each router host should have it's own Redis instance local to that host.
  This redis instance then is a slave of the master instance. This is for
  several reasons:

  #. The round trip for quering the instances is reduced because the requests
     do not leave the machine.
  #. Isolated router hosts can continue to route even if the pacemaker
     temporarily dissapears.
  #. Redis handles reconnecting to the master when it becomes available again,
     and handles replicating the appropriate entries to the slaves.

Statistics
----------

As previously mentioned, NGINX logs a special access log, that logs in JSON
instead of a normal access log. This is done so that the log file is easier
to parse to read the stats. There is no magic to make NGINX log in this format;
it's just a standard custom format.

NGINX can't log directly into the Redis instance. During the log stage of a
request, LUA scripts can't create TCP sockets. So instead the log file has to
be written and read later.

Paasmaker, by default, checks the log file for changes every 500ms. This keeps
the stats very much up to date, but is not expected to scale for very large
installations.

The Redis instance for stats is seperate from other Redis instances. It is
not incorporated with the routing table instance, because the stats would then
be replicated to other routers - which is not desirable, because the updates
to the routing table should be the only thing replicated, to improve the replication
speed.

Classes
-------

The following classes form the core of the routing system and the stats fetching.

.. autoclass:: paasmaker.router.router.NginxRouter
    :members:

.. autoclass:: paasmaker.router.router.RouterTest
    :members:

.. autoclass:: paasmaker.router.stats.StatsLogReader
    :members:

.. autoclass:: paasmaker.router.stats.StatsLogPeriodicManager
    :members:

.. autoclass:: paasmaker.router.stats.ApplicationStats
    :members:

.. autoclass:: paasmaker.router.tabledump.RouterTableDump
    :members:

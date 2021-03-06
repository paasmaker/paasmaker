
Routing System
=================

HTTP requests are routed inside the system with several components:

* A NGINX server runs an embedded LUA script.
* The LUA script connects to the router table Redis that stores
  a mapping of hostnames to instance addresses. It also outputs
  several keys that allows logging the request to the appropriate version
  type, node, and instance. See the section below for a list.
* Once the request is complete, NGINX logs the request to a file.
* The access log file is adjusted to write out JSON lines instead
  of the normal plain text.
* Another process comes along and reads the access log file and inserts
  the results into another redis instance.
* Pacemakers update the routing table as instances are started or stopped,
  or errors detected.
* Each router host should have its own Redis instance local to that host.
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

Router hostname lookup
----------------------

The following actions are taken to look up the hostname of the incoming
request to route it through to the correct location:

* Finds the hostname of the request. For example, `www.foo.com`.
* Sees if it can find routes for `www.foo.com`.
* Sees if it can find routes for `*.foo.com`. Note that this only works
  on a single level for performance reasons - so baz.bar.foo.com will only
  try to look for `*.bar.foo.com` in the database.
* Finds the log recording key for the hostname, used to track the stats
  for that instance type.
* Where it finds routes, it chooses one at random, and directs the request
  to that instance.
* It then logs to result of that request to file with the appropriate logging
  key, so that request can be accounted to a specific instance type.

In future, we hope to be able to support more features with the router, such
as sticky sessions, detection of down instances at the router level, and other
traffic balancing features and methods.

Redis key layout - Routing Table
--------------------------------

The router uses the following keys to store routing table data. It's documented here
to make it easier to understand what the code is trying to do, and also to assist
if you are trying to look at the data directly in redis.

instances:<hostname> (SET)
    This key is a set of instance addresses and logging information for that route.
    This data is combined together to keep all the data together for the routers, and
    remove the need for a second round trip to collect the logging keys. Each entry
    in the set looks like this::

        <address>:<port>#<version type id>#<node id>#<instance id>
        An example: 127.0.0.1:42600#1#1#1

    The set key name includes the full hostname of the entry, and this is used to
    match up the hostname with the set of instances that match it.

instance_ids:<hostname> (SET)
    This key contains a set of instance IDs for the given hostname. For each entry
    in this set, there will be an entry in the instances:<hostname> key. The set
    is not ordered so you can't directly match them. The intended use for this key
    is to check that the routing table is correct.

serial (INTEGER)
    This key is an incrementing number. Each time the routing table is updated, this
    number is incremented. The idea is that this can be compared to the serial on
    the router nodes to make sure that they're replicating the routing table correctly.

Redis key layout - Stats
------------------------

The stats instance stores accumulated stats for the router. It's done in such a way
that remote routers can insert their records when they're ready. Ideally this will
be done in real time, but routers can catch up later if they lose connectivity or
are isolated for any reason.

position:<nodeuuid> (INTEGER)
    This key indicates the number of bytes into the stats log that's been read and
    parsed. Each node that contributes log stats updates this, and uses it to keep
    a track of where it's read up to. If a node can't report in for a while, it can
    use this to catch up when it can report in.

stat_vt:<application version type id> (HASH)
    This key is a hash that contains the various stats for the given version type ID.
    This records only total stats for that version type ID. The keys stored are:

    * requests: the total number of HTTP requests.
    * bytes: the total number of bytes transferred.
    * timecount: the number of summed time entries
    * time: the total time, in milliseconds, spent on requests. Divide by
      timecount for a global average time. (Requests that were not delivered
      won't record a time, thus the need for timecount).
    * nginxtime: the total time, in milliseconds, spent by nginx. Divide by
      requests for a global average time.
    * 1xx/2xx/3xx/4xx/5xx: the number of requests that fell into the given
      response codes.
    * 100/101.../599: the individual response codes are counted as well, but
      may or may not be set. You can test for these if you're interested. These
      are not currently exposed via the API or tools.

    The "vt" in the key stands for "version type" - that is, an ID that matches
    objects in the ``ApplicationInstanceType`` table.

history_vt:<application version type id>:<unix hour timestamp>:<metric> (HASH)
    These keys store historical values for a metric, in hourly buckets, down
    to the second resolution.

    * <application version type id>: this is the numeric application version
      type ID.
    * <unix hour timestamp>: this is the unix timestamp of the request, mod 3600.
      This thus sorts the values into hourly buckets.
    * <metric>: this is one of the metrics that we record history for. It is one of
      requests, bytes, timecount, time, nginxtime, 1xx, 2xx, 3xx, 4xx, or 5xx.

    The key is a Redis hash construct. Inside the hash, the keys are the actual
    unix timestamp of the measurement, and the values the value. This is not
    the most efficient storage method (because to get any range you have to fetch
    the whole hour, or multiple hours from multiple hashes) but should be fast
    enough for the moment.

history_vt:<node id>:<unix hour timestamp>:<metric> (HASH)
    These keys are the same as history_vt, except they're for a single node instead
    of an application version type.

workspace:<workspace id> (SET)
    This key contains a set of all application version type IDs that appear in the
    given workspace. It can be used to get a list of version type IDs to aggregate
    to get all the stats for that workspace.

application:<application id> (SET)
    This key works the same as workspace:<workspace id>, except it contains the version
    type IDs for an application.

version:<version id> (SET)
    This key works the same as workspace:<workspace id>, except it contains the version
    type IDs for a version.

node:<node id> (SET)
    This key works the same as workspace:<workspace id>, except it contains the version
    type IDs that have run on the given node ID. The node ID is it's numeric database ID,
    not it's UUID.

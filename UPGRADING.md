Upgrading Paasmaker
===================

At the time of writing, Paasmaker does not have formal releases. When it does,
a proper guide will be written for each release. In the meantime, here are some
notes on how to get through particular commits.

Revision 457d353b, September 28th, 2013
---------------------------------------

Redis Upgrade. The version of Redis was upgraded in this version and tested.
If you updated past this version, everything on an existing system will continue
to work. However, to take advantage of this, you can follow the following steps
to upgrade your Redis instances.

NOTE: This does involve some downtime.

* You will need to do this on each node that runs a Redis instance - Pacemakers
  and Routers.
* Run the installer again using the same configuration file you used originally.
  This will download and build the new version of Redis for you.
* Stop Paasmaker on the node.
* Terminate gracefully any running Redis instances. You can locate them as follows.
  Don't send a -9 signal to them - otherwise you will lose data. A normal kill
  signal will allow Redis to save it's data first.

        $ ps aux | grep redis-server
        ...
        daniel   21347  0.0  0.0  35020  1704 ?        Ssl  08:52   0:00 thirdparty/redis-2.6.16/src/redis-server /tmp/tmpdNeWxG/redis/jobs/service.conf
        ... there will be three of these ...
        $ kill 21347

* Restart the Paasmaker node. Paasmaker will restart the new Redis version as
  it starts. The data will be read from the existing files.
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

Revision 5706328f, September 28th, 2013
---------------------------------------

Password hashing update. The method used to hash passwords was updated. The previous
method wasn't insecure, but it wasn't a strong as it could have been. This update fixes
that.

The update requires a new Python library. Re-running the installer with the same
configuration file you used originally will add the missing dependency.

Passwords set prior to this release will continue to function as normal. However, as
you change passwords they'll be stored with the new hashing method.

Revision bc887653, October 5th, 2013
------------------------------------

In this revision, the database schema was updated. Prior to this release, Alembic
had been included but not set up correctly for database migrations.

In this revision, the database is automatically created only if it doesn't exist.
Otherwise, you'll need to run a migration to update it to the current version.

From the root directory, you can run these commands to update your schema to
the latest version:

    $ . thirdparty/python/bin/activate
    $ alembic upgrade head
    $ deactivate

You don't need to stop your Paasmaker node to do this, although you will need
to apply the migration before restarting Paasmaker, otherwise it will fail to
start.
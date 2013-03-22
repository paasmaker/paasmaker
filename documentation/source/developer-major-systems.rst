Major systems
=============

This document is meant to lay out some of the major internal components of
Paasmaker. It is a work in progress at this stage.

Configuration
-------------

A single instance of :class:`paasmaker.common.configuration.Configuration` is
created when the server starts, and is passed in to most objects in the system.
The reason an instance of this object is passed around is to allow a similar
object, :class:`paasmaker.common.configuration.ConfigurationStub` to replace it
for unit tests.

The ``Configuration`` object does more than it should, but is the central resource
for fetching:

* Database sessions.
* System configuration.
* Access to Redis.
* Plugins - creating and checking them.
* Job manager - accessing it.
* Instance manager.
* Propagating job statuses.

The object handles loading the configuration from the ``paasmaker.yml`` file,
and registering the initial plugins, merging the default set with the set from
``paasmaker.yml``.

Job Manager
-----------

The job manager runs on a few core concepts:

* Jobs are assigned a globally unique job ID (provided by Python's UUID library),
  and they come in this format: ``39d4f79d-2196-4d80-9cf8-fe18c4c27618``.
* A specific job is assigned to a particular node. It's up to that node
  to process that job once it has been assigned to that node.
* Every job has a log file that the job tasks will write to as a record
  of what that job did. The log file exists on the node that processes the job;
  however, the nodes all have a websocket server that can stream the log files
  to any other node. The idea behind this is that the user can see, anywhere on
  the cluster, the real time log status of a job.
* Jobs are arranged into trees. When working with jobs, the whole tree is worked
  on instead of an individual job. The root job's ID is considered the ID for that
  whole tree.
* When jobs are placed into a tree, the leaf jobs are executed first. If multiple
  jobs are on the same leaf, they are executed in parallel. Once all child jobs
  are completed, the parent level and parent jobs are executed, and so forth
  up the tree until all the jobs are completed. This is a dependency system
  to allow certain actions to occur successfuly before other actions are performed.
* If a job fails with an error, all running jobs in that tree are asked to abort, and all
  jobs that have not yet run are placed into the aborted state and are not started.
* A user can request to abort a specific job, which acts the same way as if a job
  fails. This will stop any running jobs, and mark all other waiting jobs
  as aborted so they don't start.
* Job trees have tags on them, so they belong to a combination of a workspace,
  application, application version, instance, or node, so they can be sorted
  through quickly to find relevant job trees.

Currently, the jobs system uses a Redis server to store it's job data, and uses
Redis's built in Pub/Sub system to message other nodes when jobs change status.
The choice of using Redis to store jobs means that the Job manager Redis becomes
a point of failure; however, applications will continue to run whilst the Redis
is unavailable, but no more jobs can be started. It is expected that a system
administrator will be notified in this case and can take corrective action within
a short period of time.

The configuration object holds onto an instance of :class:`paasmaker.common.job.manager.JobManager`
in the instance variable `job_manager` and can be accessed via that.

The Job manager contains a watchdog that checks every few seconds to make sure that it
is still connected to the jobs Redis, and if not reconnects. This allows the master
node to go away for a while and come back.

BaseController
--------------

All HTTP controllers are API or web control endpoints. A full treatment of this is in the
:doc:`developer-controller` document.

Node Registration
-----------------

The Pacemaker will make it's decisions on what actions to take based on the data
recorded in it's SQL database. This means that it needs to know what nodes are available,
and the status of each instance on that node.

The current system to do this is crude, but has the advantage of staying in sync
even with connection failures.

When a node first comes online, it immediately registers with the master node.
The master node assigns that node a UUID, and creates a record in the SQL database
for that node. The node then assumes the identity given to it by the UUID,
although this is not a secret or trusted value; the Pacemaker does some additional
checking when update requests come in.

Periodically, nodes report in by using the same request as the registration. The
only difference is that the UUID is reported back for updates. By default this
is every 60 seconds. If a node can't report back, it just waits until the next
interval to try again.

Registration in Paasmaker started off quite simply, but ended up getting more
complex, and now does more than it should, but the system works for the time being.
Basically, a node reports it's entire state during registration so as to keep
the Pacemaker up to date.

The following data is reported to the master during a registration update:

* Node tags; which are a composite of tags from ``paasmaker.yml`` and any
  tags generated by dynamic tags plugins. Dynamic tags are only generated
  once during node startup and the same tags are returned afterwards.
* Node stats; which are generated by the stats plugins.
* Instance states. For every registered instance, it returns the UUID
  of that instance, and the state of that instance. The pacemaker then
  makes sure that it's database is up to date, or depending on the state
  change, takes a corrective action immediately.

Nodes can report in more often than their timer. In fact, in most cases
they will. As soon as the instance manager's ``save()`` method is called,
it will trigger a report to the master node to update the SQL databases's
state. This is a crude system, but it prevents lost or unsynchronised
updates from the heart's instance management system, as each node will
retry to send the instance states when it can.

Database model
--------------

Only Pacemaker nodes have access to the SQL database.

Internally, we are using the SQLAlchemy library to model the objects in
the database. All the model files are stored in ``paasmaker/model.py``,
and all ORM objects descend from :class:`paasmaker.model.OrmBase`, which
provides some automatic timestamp fields and convenience methods for other
objects.

A diagramatic form of the model looks like this:

.. image:: images/database-model.png
	:alt: Database model diagram

You can see the reference for all the model classes and any helper functions
that each one has on :doc:`the reference page for the model classes <developer-model>`.

Instance manager
----------------

Every heart node has an instance manager. Because Heart nodes don't have access
to a database (and using any kind of database is overkill for them), they use the
simplest possible data storage format available: a flat file on the filesystem in
JSON format. Each heart only stores instance data for its own node, and if the data
is lost (as in if the node completely fails) then there is no major data loss, as
Paasmaker is designed to have failed heart nodes replaced.

The class :class:`paasmaker.heart.helper.instancemanager.InstanceManager` looks after
the catalog, serializing writes to disk of the catalog as it's updated. It also generates
the reports that are sent back to the master node periodically. The instance is available
as the ``instances`` instance variable on the ``Configuration`` object.

Currently this object also checks all instances on startup and shutdown, and makes
adjustments based on the configuration.

Health manager
--------------

One of the core features of Paasmaker is the ability to work around failures within
certain limits. These are controlled by plugins, which can check the state of the system
and then make changes.

The health manager makes it's decisions based on the state of the system as it appears
in the SQL database, so it's key that the database is up to date. The node registration
is designed to keep the database as up to date as possible.

The class :class:`paasmaker.pacemaker.helper.healthmanager.HealthManager` is responsible
for launching health check groups periodically. In the server configuration, a series of
health check groups are defined like this:

.. code-block:: yaml

	groups:
	- name: default
	  title: Default Health Check
	  period: 60
	  plugins:
	    - plugin: paasmaker.health.downnodes
	      order: 10
	      parameters: {}
	    - plugin: paasmaker.health.routerdowninstances
	      order: 10
	      parameters: {}
	    - plugin: paasmaker.health.adjustinstances
	      order: 20
	      parameters: {}
	    - plugin: paasmaker.health.stuckjobs
	      order: 20
	      parameters: {}

You can define as many groups as you need, and they are queued up as a job. The health
manager sorts these groups by their order. Plugins with the same order run at the same
time, and lower orders run first.

In this default health check, it runs the down nodes check first. This plugin looks
for nodes that haven't reported in recently, and marks them as down. It then adjusts
any instances in the database on that node to down. Then, the adjust instances health
check will run later (as it's got a higher order) and will calculate if any more instances
are required and start those up.

The key point is that each health check gets it's own job tree, which allows the progress
of active health checks to be monitored, and also historically allows you to see what the
results of past health checks were.
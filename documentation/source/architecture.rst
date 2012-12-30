
Architecture
============

This document describes the architecture of Paasmaker.

Core Components
---------------

At the core of Paasmaker, is three major subsystems.

Router
	This component manages the associated router on that node,
	which directs incoming HTTP requests to an instance that can
	service the request, based on the hostname.
	It reads and processes stats for the router, and ensures
	that the routers Redis instance is up to date with the master.
	There can be as many routers as is required for a cluster.

Heart
	This component manages :ref:`instances <glossary-instance>` - starting
	and stopping them on request, :ref:`registering <glossary-registering>` them
	on nodes by downloading the files, and managing their state when
	the heart itself starts and stops. There can be as many hearts as
	required for a cluster.

Pacemaker
	This component coordinates all other nodes and roles. Nodes register
	with the Pacemaker, and the Pacemaker also runs the web and API front
	ends to the cluster that allow you to manage it. In the initial release,
	only one Pacemaker in the cluster is supported, but in the future it
	will be possible to have more than one Pacemaker in the cluster.

In the future, Paasmaker will be extended to have a fourth component:

Service
	This component will advertise any available :ref:`services <glossary-service>`
	on the node, and then perform any related tasks with those services to be able
	to provide them to applications.

Organisation
------------

The following organisation is used to classify everything into the system:

* **Workspaces**: Workspaces are the top level construct in the system. They contain
  a number of applications. Permissions are attached at the workspace level and apply
  to everything underneath.
* **Service**: a service is a named resource that an application can use, and the
  credentials for which are supplied to the application automatically. For example,
  a MySQL database is a service, as is a PostgreSQL database. Paasmaker manages
  creating these databases for you. A service is unique per workspace.
* **Application**: an application is a named collection of versions and services. An
  application name is unique per workspace. This, coupled with the fact that services
  are unique per workspace, allows to you have a staging and production workspace on the
  same cluster of servers, but have them be completely seperate.
* **Application Version**: a numbered version of an application, typically a specific
  revision from the source control system.
* **Application Instance Type**: inside each version are instance types - that is,
  different parts of your application started from the same code base. For example,
  you might have a public web site, an administrative website, and a background
  task processor in the same code base. Each instance type can have a different runtime,
  and other protections between versions. See :ref:`instance types <glossary-instance-type>`
  for more information on this.
* **Instance**: an instance is a version of an instance type running on a specific node.
  An instance has a state, and that state indicates what the instance is doing at the time.

In addition to the application infrastructure above, the following exists to manage
the remainder of the cluster:

* **Nodes**: each node is known to the system, including it's status, it's roles,
  and any runtimes and versions of those runtimes.
* **Users**: each user has their own login to the system. The database will have a
  record of each user, however, they might be authenticated by an external database
  such as an LDAP server.
* **Roles**: each user is assigned a role, which has an associated set of permissions
  that allows them to perform actions in the system.
* **Role allocation**: A user is assigned a role either with a specific workspace,
  or on the entire cluster.

Clustering
----------

One of the core design goals of Paasmaker is clustering, and being able to do this
easily from the beginning.

To support this goal, a number of internal systems are present that allow the nodes
to communicate with each other in a robust way, but also to be able to clearly
show what is occuring.

Each node has a HTTP API endpoint which can be used to communicate with it. This is
used by the Pacemaker to accept user requests, and for other types of nodes, to
check that they are healthy and still running.

To start and stop tasks and collect logs, the distributed jobs system is used
to collect and record job statuses across the cluster.

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
* If a job fails with an error, all running jobs are asked to abort, and all
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

Instances
---------

Each application is organised into instances. Instances are the actual running
application on the cluster, that can service HTTP traffic (although instances
can be standalone, meaning that they do not need to serve HTTP traffic).

The core idea is that each instance should have its own, paasmaker-allocated
TCP port that speaks HTTP. For many types of applications, this is an appropriate
built in HTTP server for each application. For PHP, this is an Apache instance
with a virtual host configured to listen on the assigned port. For Python Tornado
applications, this is an instance of the application listening on a TCP port.
For Ruby applications, this might be a Thin application server listening for
requests.

Instances can start and stop based on user requests, replacement for failed
instances, or in response to load to scale up to meet demand, or scale down
as demand subsides.

Once instances are running, the routers can then route HTTP traffic to them.

Routing
-------

A core part of Paasmaker is routing incoming HTTP requests to a node that
can service that request. The determination needs to be made quickly,
as the idea is to add as little overhead to your HTTP request as possible.

The routing component uses NGINX with an embedded Lua script, which talks
to a Redis database to look up the routes for a given hostname. Each router
will have it's own complete copy of the routing table in a local Redis instance,
which is a slave of the master routing table. If the master routing table goes
down, each router can continue to route on the last version of the routing table,
and will then resync with the master when it becomes available again. Also,
running a Redis locally speeds up the lookups as packets do not need to leave
the machine.

The routing table contains only routing entries. It is not shared with
the stats or job Redis, to keep it's size down to a minimum, for faster
replication updates.

The router does a few lookups to be able to service a request. These are done
in a Redis pipeline connection to reduce the number of round trips. In future,
it might be able to do more, but this will need to be balanced carefully
with the performance of the router.

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

Security and Mutli-tenancy
--------------------------

Paasmaker has (at this time) been designed to run in small clusters, with
applications that you trust. In the default setup, all components of the system
run as the same user; and applications do not have any specific restrictions
on file access. So there is little to stop an application from reading your
Paasmaker configuration file or meddling with other Paasmaker related files.

User passwords are stored in the database with a per-user salt, which will
make them difficult to crack even with the hash. Other access information,
such as the super token, are stored in the configuration file in plain text.

Only Pacemaker nodes need access to the SQL database. The Job Management
system uses a seperate Redis, which does isolate other nodes somewhat.

In the future, Paasmaker will likely be altered to have better protections
for this. One way to do this would be to run the node with root permissions, and
have it drop to a seperate non-privileged user for various application actions
- although this will have it's own set of concerns and issues.

For now, you can do several of the following things to work around this issue:

* Seperate the Pacemaker and the heart nodes onto seperate hosts. Hearts do not
  need to have or know the cluster's super token, and even with the Node token,
  can only take a few specific cluster actions.
* As an enhancement to the above, you can disable prepare commands by simply
  not registering any plugins that are able to run prepare commands. You will
  obviously lose this functionality in this case.
* Don't run untrusted applications at this time.
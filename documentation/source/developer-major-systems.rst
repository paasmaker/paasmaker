Major systems
=============

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

BaseController
--------------

A full treatment of this is in the :doc:`developer-major-basecontroller`
document.
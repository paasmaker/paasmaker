Runtime plugins
===============

Paasmaker is designed to allow new runtimes to be added by simply adding a plugin.
This document covers some details about runtime plugins and how to write them.

The goal of any runtime plugin is to take a directory containing source code
(supplied by Paasmaker), and start or run that application, with it responding
to HTTP requests on a TCP port supplied to the runtime by Paasmaker.

The only exception to this are standalone instances, which are basically daemons
that run in the background and do not listen for HTTP requests. Runtimes should
support both HTTP and standalone instances where possible.

Runtime Strategies
------------------

Currently, the runtimes shipped with Paasmaker take one of two strategies to
run applications:

1. Start up the application in a standalone fashion, that can respond to HTTP
   requests. A component known as the command supervisor keeps an eye on the
   application, and can be used to stop the application, or report to the node
   when the application exits for any reason.

   For example, the example Redmine guide uses ``thin start -p <port>`` to start
   the application. This uses the `Thin <http://code.macournoyer.com/thin/>`_
   Ruby application server to start the application. Thin will start listening
   on the supplied TCP port for requests.

   Applications are then stopped by killing the appropriate process ID.

2. Start up a daemon that can manage several applications at once, via configuration
   files. The runtime then will know how to write new configuration files, and
   reload the daemon as appropriate. On the other side, it will know how to remove
   the configuration and reload the daemon again.

   For example, the PHP runtime starts up a single Apache instance per node.
   For each application, it writes out a new virtualhost file for that Apache,
   and then asks Apache to graceful itself. This helps conserve resources on
   servers running a lot of PHP applications, as each additional Apache instance
   would consume shared memory - the default on Ubuntu only allow you to run
   approximately 5 Apache servers before this runs out (and thus, would limit
   the server to only 5 PHP instances at a time). The downside to this is that
   all the applications depend on a single Apache instance - so once all the
   connection slots are used (the default is 150), some applications might be
   unreachable.

The Command Supervisor
----------------------

A component of Paasmaker, called the Command Supervisor, is intended to provide
some common helpers for running applications and keeping a track of them.

The basic flow of using the command supervisor is as follows:

* When starting an application, the command supervisor is invoked with configuration
  that tells it what to do. Generally, this is the command to run, and the shell
  environment to run that command in.
* The command supervisor is in a seperate script called ``pm-supervisor.py``. Paasmaker
  starts this script in the background. This is done so that the Paasmaker server on the
  node can be restarted and allow applications to continue to run (and be monitored to some
  extent). Note, this obviously doesn't mean applications can continue to run after
  a server reboot.
* The command supervisor then starts the command supplied, and then waits for one of
  two conditions:

  1. The supplied command exits. It makes a note of the exit code, and then passes
     that back to the Heart on the same node, which then updates the instance state
     and contacts the Pacemaker to allow it to decide what to do next. It contacts
     the local heart via HTTP, authenticated with a one-time-use code given to it
     when the instance started. If it can't contact the Heart after a few attempts,
     it writes the exit code to a location on the filesystem, so that the Heart can
     read this on next startup and take the appropriate action.

  2. The ``pm-supervisor.py`` script receives a SIGTERM. This is how Paasmaker indicates
     that the instance should shut down. ``pm-supervisor.py`` then sends the instance
     that it's looking after a SIGTERM, which allows it to shut down normally and exit.
     Once it has exited, it will send the command return code to the managing Heart,
     which can take an appropriate action.

The base runtime provides helpers to interact with the command supervisor easily.

RUNTIME_EXECUTE, RUNTIME_VERSIONS, and RUNTIME_ENVIRONMENT
----------------------------------------------------------

All of the runtime modes have a common base class - BaseRuntime. If your plugin
doesn't implement all of the modes RUNTIME_EXECUTE, RUNTIME_VERSIONS, and RUNTIME_ENVIRONMENT
(although currently it needs to), you will need to alter your classes plugin modes.

.. NOTE::
	Runtime plugins run on both Pacemaker and Heart nodes. It may run on Heart
	only nodes, which means that the plugin can't access the SQL database at all,
	and should not need to. It can access the jobs system but again should not
	need to.

.. autoclass:: paasmaker.heart.runtime.base.BaseRuntime
    :members:
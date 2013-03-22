Introduction to Paasmaker
=========================

What is a Platform as a Service (PaaS)?
---------------------------------------

Wikipedia defines a PaaS as "`a category of cloud computing services that
provide a computing platform and a solution stack as a service <http://en.wikipedia.org/wiki/Platform_as_a_service>`_".

That is, a system that can take your application, provision any resources required to
run that application (such as databases), and then organise to run that application,
and in the case of Paasmaker, route HTTP requests to it.

Why use a Platform as a Service?
--------------------------------

In traditional web development, you have a set of files (and possibly data) that
form your application or website. Then, you have a database that you connect to
and store data in. The code provides some kind of website, and possibly background
tasks such a cron jobs, or backround workers to do offline processing.

Traditionally, to go live with these, you need to create the appropriate databases,
choosing usernames, passwords, and database names. Then, you select a location for
the files, and set up the appropriate stack to host your application, and set up
ways to start it. You also decide how to run background tasks and cron jobs, and
edit the appropriate configuration files to set this up. Optionally, once you've
defined all this, you then come up with a strategy to update the application as you
make changes. You then test that all the components work together, and go live.
Often some of these steps are automated by various scripts or systems that are
designed to automate these tasks and there are many excellent systems to do that
out there.

There are plenty of different web stacks to host your application on (for example,
Apache and mod_php for PHP applications, or Apache and mod_passenger for Rails/Ruby
applications). Each one has a different way to set them up, different considerations
to take for performance, and if you want to have a machine hosting a mix of these
applications (in different languages, or just different versions of each language),
you need to figure out how to get them all to work together properly.

Then comes scaling. If you want to spread your application across multiple machines,
you'll need to configure several machines with your application. After that, you'll
need to route HTTP requests to those machines. Finally, you'll need to have a plan
or system in place to handle failover, or some way to disable traffic to a specific
failed machine.

A Platform as a Service is designed to assist with solving some of these problems.
Specifically, it can allocate databases for you and provide that to your application.
It can take your application code and choose servers for it to run on, and ask that
server to run the application. It can also provide ways to isolate different runtimes
(languages that your application is written in) and versions. It can also detect and
route around failures, and redistribute your applications if needed - or even just add
more capacity automatically as your application needs it.

What limitations are there in using a Platform as a Service?
------------------------------------------------------------

A Platform as a Service is not a magic bullet. No technology really is. To allow the
Platform as a Service to perform it's job, you will need to consider a few aspects when
writing your application to get the most out of it.

* PaaSs are designed to scale your application horizontally, rather than vertically.
  That means that it will run your code on more servers to meet demand, rather than
  finding a bigger server to run your application on. For that reason, the application
  code should be considered as immutable. That is, you should not store permanent data
  on the filesystem alongside the application code. This is because the PaaS will delete
  an instance of your application when it's no longer required on a specific server.
  Also, each instance of your application that the PaaS starts has it's own seperate
  filesystem - which might well be on different physical servers.

  This might seem like a huge limitation of the system. And for certain applications
  and hosting systems, it is. Older CMS applications, like Drupal, Wordpress, and Joomla,
  expect to be able to store uploaded media onto the filesystem and have it be persistent.
  Paasmaker can be made to host these CMS systems, but it is not the primary focus of
  Paasmaker, and you should carefully consider your application and it's needs.
  However, having said that, there are plugins for each of these CMS systems that can
  instead store these files on a service like Amazon S3, which is designed for long term
  storage. Another solution for this is to set up your servers with a shared filesystem -
  either using a traditional NFS setup, or something clustered like Gluster.

  Most applications store their user data in databases of some kind - either a relational
  SQL database or a NoSQL database, or an external web service. These applications are
  quite easy to run on a PaaS.

  There is nothing stopping your application from writing files to it's filesystem; and
  in fact you might like to write temporary cache files, that you can easily generate,
  onto the filesystem to speed up your application, knowing that they will vanish when
  a new version is deployed or more instances started.

  Paasmaker has the concept of a "filesystem" service, that can be used to host some legacy
  CMS applications on a single node. However, these applications will not be able to scale
  unless they are updated to use a shared filesystem of some kind.
* The PaaS will choose the TCP port that your specific application will run on. It will
  provide to you the port that you should use when your application starts. This is
  so that the PaaS can run several of the same application on a single node, and ensure
  that several different applications on the same node to not conflict.
* The PaaS will choose a server for your application to run on. The idea here is that
  the PaaS then has the power to rearrange applications to work around failures or balance
  the load across the system. Paasmaker does allow you to give hints about where to place
  applications, either by node tags or custom placement plugins.

  If your tasks rely on being on a specific server, either because that server is set up
  in a particular way, or that the IP of a given server is whitelisted to access a remote
  service but other servers are not, you will need to arrange a way to fix these things.
  In the case of the servers being set up in the same way, systems such as Opscode's Chef
  or Puppet can be used to keep a set of nodes up to date.

As with any technology, you will need to evaluate it closely to make sure it matches your
use case.

However, quite a number of modern web applications are already being written and designed
for cloud hosting systems that horizontally scale; a PaaS is just designed to make
scaling them easier, and a lot less work.

What benefits can a PaaS provide?
---------------------------------

A PaaS can make a few things easier for you:

* Allows you to write applications and not have to hard code configuration (such as database
  connection details) into the files. These configuration details are provided to the application
  at runtime, reducing the likelyhood of mixing up development, staging, and production database
  details.
* Choose the best location to run your application, and easily choose several hosts to run
  your application for you. It can then set up the HTTP routing for you automatically, and
  adjust it in the case of server failures.
* Provide a simple interface for users who are not system administrators, to be able to easily
  access and deploy applications on production infrastructure.

What is Paasmaker?
------------------

Paasmaker is an open source Platform as a Service. It is designed with several key goals:

* Be simple for users to access and interact with, by providing a web interface, and a simple
  set of user permissions. However, it also provides a full API so it can easily be integrated
  into other systems or controlled from the command line instead.
* Be highly visible in all it's activities; always let the user know clearly what the system
  has to do, and what it's doing, and the exact, up to the second updates on any tasks that
  it is currently running. Also, it is designed to show clearly the realtime traffic to
  applications, so you can see what is being used and how.
* Allow customisation via plugins, to allow developers or System Administrators to extend
  the system easily.
* Provide System Administrators with options about how to set up their systems. Plugins are
  registered with symbolic names, which allows System Administrators to expose services to users
  in either generic or highly specific ways.
* Be as simple to install as practically possible, whilst still giving control over how the
  system is deployed. This includes the core system, and also any runtimes (languages) that
  the system supports.
* Integrate well with Source Control Management systems, and try to promote deployment directly
  from source control systems.
* Allow you to use the PaaS on your own desktop machine, alongside your existing development
  environments. It can also make it easier to set up your own development sites for projects,
  by handling the database setup for you.

Next steps
----------

To get started with Paasmaker, read the :doc:`installation guide <installation>`.
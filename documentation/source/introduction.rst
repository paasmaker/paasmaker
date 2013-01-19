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
designed to automate these tasks.

There are plenty of different web stacks to host your application on (for example,
Apache and mod_php for PHP applications, or Apache and mod_passenger for Rails/Ruby
applications, or gunicorn for Python applications). Each one has a different way to
set them up, different considerations to take for performance, and if you want to
have a machine hosting a mix of these applications (in different languages, or just
different versions of each language), you need to figure out how to get them all to
work together properly.

Then comes scaling. If you want to spread your application across multiple machines,
you'll need to configure several machines with your application. After that, you'll
need to route HTTP requests to those machines. Finally, you'll need to have a plan
or system in place to handle failover, or some way to disable traffic to a specific
failed machine.

A Platform as a Service is designed to handle some of these problems for you. Specifically,
it can allocate databases for you and provide that to your application. It can take
your application code and choose servers for it to run on, and ask that server to
run the application. It can also provide ways to isolate different runtimes (languages
that your application is written in) and versions. It can also detect and route
around failures, and redistribute your applications if needed - or even just add
more capacity automatically as your application needs it.

What limitations are there in using a Platform as a Service?
------------------------------------------------------------

A Platform as a Service is not a magic bullet. No technology really is. To allow the
Platform as a Service to perform it's job, you will need to consider a few aspects when
writing your application to get the most out of it.

* The application code should be considered as immutable. That is, you should not
  store permanent data on the filesystem alongside the application code. This is
  because the PaaS will delete an instance of your application when it's no longer
  required on a specific server. Also, each instance of your application that the
  PaaS starts has it's own seperate filesystem - which might well be on different
  physical servers - and you might have several instances of an application to meet
  load or redundancy requirements.

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
  unless they're updated to use a shared filesystem of some kind.
* The PaaS will choose the port that your specific application will run on. It will
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

* Be simple for users to access and interact with, by providing a feature complete web
  interface, and a simple set of user permissions. However, it also provides a full API
  so it can easily be integrated into other systems or controlled from the command line instead.
* Be highly visible in all it's activities - always let the user know clearly what the system
  has to do, and what it's doing, and the exact, up to the second updates on any tasks that
  it is currently running. Also, it is designed to show clearly the realtime traffic to
  applications, so you can see what is being used and how.
* Allow customisation via plugins, to allow developers or System Administrators to teach the
  PaaS new tricks easily.
* Provide System Administrators with options about how to set up their systems. Plugins are
  registered with symbolic names, which allows System Administrators to expose services to users
  in either generic or highly specific ways.
* Be as simple to install as practically possible, whilst still giving control over how the
  system is deployed. This includes the core system, and also any runtimes (languages) that
  the system supports.
* Integrate well with Source Control Management systems, and try to promote deployment from
  source control systems.

Why was Paasmaker written?
--------------------------

The original author of Paasmaker worked in Digital Marketing, as a System Administrator
looking after hosting systems. Digital Marketing has some slightly different hosting
requirements than some other companies and industries. The websites are an eclectic mix
from many different clients, that served many different purposes. Generally, though,
websites fell into a few categories:

* Short term campaign sites, often involving competitions.
* Landing pages.
* Corporate websites.
* e-Commerce.

Each of these categories has slightly different requirements, which affect how they are
hosted.

**Short term campaign/competition sites** are generally written as completely bespoke code,
to implement the competition or campaign that they cover. They're often written quite quickly,
generally coded from start to finish in the matter of a few weeks. They're highly specific to
the client or the competition. When the campaign or competition is launched, they fetch a lot of
traffic in a short period of time - the kind of traffic that is well known to take down web servers.
These sites are quite critical in this stage; the client generally has organised and paid to advertise
the site. If customers come along and receive an error, they are unlikely to return, which means
money wasted advertising or sending mailouts. As the campaign goes on, the traffic generally slows down,
but is often well above a typical website for an agency. When the campaign finishes, clients
like to have the site continue to be online, either to announce winners or just to have other
material on them. Once the sites reach this stage, they may only recieve a handful of requests
per day, but it is important to keep them running.

**Landing pages** are generally a site with just a few pages (possibly even just one), often
with a simple call to action, or a simple signup or information form. They may not even rely on
a database at all. These little landing page sites might receive only a few hits per day,
and are often forgotten by System Administrators as they rearrange servers. Clients tend to be
the ones who notice these landing pages are missing.

**Corporate websites** are larger sites, typically based around a CMS. Because they are based
around a CMS, they often handle file uploads and storage. Many CMS systems simply store files
on the filesystem, which presents challenges in scaling these websitse. The sites are busy during the
day, moderately busy in the evenings, and very quiet overnight. These are important to keep
running as they form the online identity of the company that they represent. Occasionally,
they will have large bursts of traffic for special events or information, or even just regular
email list contacts.

**e-Commerce** sites are also on the larger side, often based around either a custom e-Commerce
platform or something off the shelf. These are quite similar in behaviour to corporate websites,
with the exception that they make money - and must be available at all times of the day and
work correctly. Also, promotions will attract a lot of additional traffic that can bring
down web servers.

The logical way to view the above types of sites is that they are all different applications,
and require different hosting systems - which on the face of it, is the correct assumption.
For example, you could host your short term campaign site on Amazon's Elastic Beanstalk service.
This would handle adding and removing front end nodes to meet your demand automatically.
Each instance of Elastic Beanstalk requires at least one EC2 instance, and it does not
support virtual hosting by default.

However, established digital agencies will manage a large collection of these sites - several
hundred is not unusual for an agency that has been running for a few years. If each site used
Elastic Beanstalk, and multiplied by a few hundred - the cost of running such an infrastructure
adds up. So agencies do virtual hosting - a single server will host many websites, and a handful
of servers will run several hundred websites.

A PaaS can assist with these issues. The concept is to have a small pool of servers, and the
PaaS can then distribute the resources as needed.

For example, when a short term campaign is launched, you can instruct the PaaS to run it across
all the nodes. Each node then takes a part of the brunt of the launch. During the campaign run,
you can reduce the number of nodes that it runs on to handle the traffic. When the campaign is
finished, you shrink the number down to one - and the PaaS will restart the application in a new
home if a server fails. As stated above, the site needs to remain running, but will only get
a few requests per day. With a PaaS, it's possible to accomplish this without provisioning any
special servers - you just use what you have, more effectively.

In the case of Corporate Websites and e-Commerce sites, you might figure that normally you only
need one server to be running that site. So you configure it as such. But then a client lets
you know that they're emailing many thousands of people a special promotion tomorrow, so to
be sure, you increase the number of instances for a while. As the promotion goes out, you can
adjust the number of instances to manage the traffic.

The idea is to reduce the number of servers required to host a large number of websites, and
give System Administrators the ability to horizontally scale applications as easily as possible,
without having to create custom sets of servers for each application.
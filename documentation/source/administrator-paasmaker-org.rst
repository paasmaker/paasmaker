
Paasmaker.org system
====================

Obviously, Paasmaker needs a hosting system for it's websites and documentation.
It would not make sense to host this on anything other than Paasmaker itself.
It also serves as an example of how to host Paasmaker in production. It is not
intended to be a best practices with Paasmaker either - it's just a suggestion
which hopefully shows the possibilities of Paasmaker.

The initial Paasmaker network looked as follows:

.. image:: images/paasmaker-org-production-layout.png
	:alt: Paasmaker initial production network layout

The basic concept here is:

* The Amazon Elastic Load Balancer is an additonal routing layer, to handle failed
  physical servers.
* The Amazon Relational Database Service provides a MySQL like database to applications
  running on the cluster. It was chosen because we can easily scale it up and down and
  is less things to maintain.
* One server, running on a small instance, is the Pacemaker, that sets up applications,
  and manages other nodes in the cluster. It also runs it's own SQL database purely for
  the pacemaker. (In this example, I used Postgres).
* One or more servers, initially m1.small to keep costs down, run as hearts and routers,
  and host applications and route HTTP traffic.

Several things needed to be chosen first before any work started. Firstly, the cluster
needs a hostname which is used to automatically generate hostnames for applications
and for the Pacemaker itself. For the production network, we chose ``production.paasmaker.net``.

Also, for this guide, everything was set up in ``ap-southeast-2`` (Sydney, Australia), because
this was the closest location for us.

.. note::
	This is purely an example of setting up a Paasmaker cluster. Your needs will be different
	to ours and you should consider this a guide to help you understand how to deploy
	Paasmaker and to design your own system. Some of the steps taken in this guide are
	purely my preferred choices in server management.

.. warning::
	At this time, you must run the SQL database for the Pacemaker on the same node as the
	Pacemaker. This is due to the fact that early on we chose to use SQLAlchemy as an ORM
	library, and this does not have any easy to implement asynchronous options for Tornado,
	the asychronous Python library in use. This made database connections very sensitive to
	connectivity issues, regardless of how brief they were. In the future, we will remedy
	this issue.

EC2 Security Group
------------------

Create a security group for the Paasmaker instances. You can take two approaches here;
either allow the security group to talk to any TCP port on the other nodes, or generate
a list of ports from the :doc:`port allocation list <administrator-port-allocation>`.

In my case, I took the easier route and allowed the instances to talk to each other
on any TCP port (internally only). From external, I only allowed port 22 (SSH) so
the nodes could be individually inspected at a later date.

So the inbound ports look as follows:

* Port 22, source ``0.0.0.0/0``.
* Port 80, source ``0.0.0.0/0``. (To allow the load balancers to work; see
  `a feature request <https://forums.aws.amazon.com/message.jspa?messageID=218840>`_ as to
  why it's open to the world).
* Port 0-65535, source ``sg-12345678`` (replace sg-12345678 with your security group ID).
* For testing, you can add access to port 42500 from your IP address only. This allows you
  to test each server as you add it to the system.

Elastic Load Balancer
---------------------

Create the Amazon Elastic Load balancer. We do this so we can point the DNS
shortly as a first step. Give it an appropriate name, and for the moment, just route
port 80 through, with HTTP (this is to preserve the original IP address information).
For the health check, I've set it to use a TCP ping instead of a HTTP ping, as the
health checks can't be set to supply a particular hostname (which is required to
get a useful response). Initially, no instances are added to the load balancer.

Summary of settings:

* HTTP on port 80 through to port 80 on the instances.
* TCP health check, every 30 seconds, to port 80.
* Response timeout 5 seconds.
* Unhealthy threshold 2.
* Healthy threshold 2.

Amazon RDS instance
-------------------

.. NOTE::
	In this example, the RDS is purely for databases for applications that you
	deploy to the cluster.

Set up the Amazon RDS instance. First, create a security group for your RDS instance,
and then launch a new RDS instance with that security group. You should adjust these
settings depending on your performance and redundancy needs.

For the security group:

* Add your EC2 Paasmaker security group to allow access.

Summary of settings:

* Database engine: MySQL.
* Database instance class: t1.micro (this is an initial size).
* Allocated storage: 10GB (adjust as per your needs)
* Database instance identifier: production-paasmaker-net (alter for your setup)
* Master username: root
* Master password: choose a password.
* Security group: the group you created before.
* No initial database.

If you don't want to use RDS, you can instead use another database server of your
choosing, and set your Pacemaker up to use that to supply services to applications.

Create Pacemaker EC2 instance
-----------------------------

Create the Pacemaker node. Create a new m1.small instance, running the latest
Ubuntu 12.04 AMI. You can fetch the correct AMI name from `Ubuntu's cloud images
page <http://cloud-images.ubuntu.com/precise/current/>`_ - although if you use the
"Launch" button next to the images, you only get a cut down set of options for launching
the instance.

For this, I've chosen a 64 bit EBS backed instance type.

Summary of settings:

* Ubuntu 12.04 server AMI.
* One instance.
* m1.small instance class.
* Shutdown behaviour: Stop.
* Increase the root volume to 10GB (or higher).
* Give it a name that is useful to you later (I used "Production Pacemaker").
* Use or create an existing keypair as appropriate.
* Select the Paasmaker security group that you created earlier.
* Launch the instance.

Once this is done, SSH to your Pacemaker instance. Use the hostname supplied
by the AWS console, and the security key you assigned to the instance.

.. code-block:: bash

	$ ssh -i <key file> ubuntu@<instance hostname>

You probably want to immediately update all packages on the system.

.. code-block:: bash

	$ sudo apt-get update
	$ sudo apt-get dist-upgrade

At this stage, you can also make any other modifications to the system
that you normally would for your standard setup. You can even install Apache,
PHP, MySQL, or Postgres as normal - Paasmaker is designed to work alongside
these on existing systems.

One thing that you'll probably like to do is install NTP, to keep the servers
synchronised correctly, which keeps all your stats accurate. The simplest
thing to do is to install NTP:

.. code-block:: bash

	$ sudo apt-get install ntp

Create the initial Paasmaker database
-------------------------------------

Create the initial Paasmaker database. Normally, Paasmaker would create databases
for you for applications, but it is unable to create it's own database. However,
you don't need to import any schema - Paasmaker will do this on first startup.

For our setup, we're going to use Postgres on the same machine as the Pacemaker.

Install the Postgres server:

.. code-block:: bash

	$ sudo apt-get install postgresql

Choose a username, database name, and password that the Pacemaker will use.
For example:

* Username: pacemaker
* Database: pacemaker
* Password: choose a password

Now go ahead and create a seperate username and password in Postgres.

.. code-block:: bash

	$ sudo su - postgres -c psql
	psql> CREATE USER pacemaker PASSWORD 'password';
	psql> CREATE DATABASE pacemaker OWNER pacemaker;

Alternately, you could use a local installation of MySQL instead:

.. code-block:: bash

	$ sudo apt-get install mysql-server
	... when prompted, choose a MySQL root password ...
	$ mysql -u root -h localhost -p
	Password: <root password>
	mysql> CREATE USER 'pacemaker'@'%' IDENTIFIED BY 'password';
	mysql> CREATE DATABASE pacemaker;
	mysql> GRANT ALL ON pacemaker.* TO 'pacemaker'@'%' IDENTIFIED BY 'password';
	mysql> GRANT ALL ON pacemaker.* TO 'pacemaker'@'localhost' IDENTIFIED BY 'password';
	mysql> quit

.. warning::
	As stated previously, using a database on different server to the Pacemaker
	node is not supported at this time.

DNS records
-----------

Set up DNS records. In this case, we're using Amazon Route 53 for DNS. In the Route 53
console you can easily point names at an elastic load balancer. Otherwise, you'll need
to set up CNAME records in your DNS system to point to the load balancer.

These are the domain names configured:

* ``production.paasmaker.net``: CNAME to your Pacemaker instance hostname. (If you use a CNAME,
  EC2 instances get the internal address, and external clients get a public address).
* ``*.production.paasmaker.net``: wildcard CNAME to the Elastic Load Balancer.

The first DNS record is used by all nodes to locate the master node. This solves a chicken
and egg issue of locating the master node. The second DNS record is used by applications
and the pacemaker itself to configure everything.

Install Paasmaker on the Pacemaker
----------------------------------

Now it's time to download and install Paasmaker on the Pacemaker node. First,
we will git clone the repository, and then customize an installation configuration
file. Finally, we'll run the installer script.

.. code-block:: bash

	$ sudo apt-get install git
	$ git clone git@bitbucket.org:paasmaker/paasmaker.git

Set up the installation configuration file. The example used for Paasmaker's production systems
is in install/configs/example-production-pacemaker.yml. You should update the file
to match your environment, but below is a copy of the file with some more descriptions.

.. code-block:: yaml

	is_heart: false
	is_router: false
	is_pacemaker: true

	cluster_hostname: production.paasmaker.net
	frontend_domain_postfix: ''

	master_node: production.paasmaker.net
	master_port: 42500

	shutdown_daemons_on_exit: false

	install_init_script: true
	enable_init_script: true
	init_redirect_port80: false

	runtime_php_enable: true
	runtime_php_disable_system_apache: true

	runtime_rbenv_enable: true
	runtime_rbenv_versions: ['1.9.3-p327']

	service_managedmysql_enable: false
	service_managedpostgres_enable: false
	service_managedredis_enable: true

	write_paasmaker_configuration: true

	extra_plugins:
	  - name: paasmaker.service.mysql
	    title: MySQL service (RDS database)
	    class: paasmaker.pacemaker.service.mysql.MySQLService
	    parameters:
	      hostname: <your rds instance hostname>.ap-southeast-2.rds.amazonaws.com
	      port: 3306
	      username: root
	      password: <password here>

	  - class: paasmaker.pacemaker.scm.zip.ZipSCM
	    name: paasmaker.scm.zip
	    title: Zip file SCM
	  - class: paasmaker.pacemaker.scm.tarball.TarballSCM
	    name: paasmaker.scm.tarball
	    title: Tarball SCM
	  - class: paasmaker.pacemaker.scm.git.GitSCM
	    name: paasmaker.scm.git
	    title: Git SCM
	  - class: paasmaker.pacemaker.service.parameters.ParametersService
	    name: paasmaker.service.parameters
	    title: Parameters Service

Then, you can install from that configuration file. This step will take a while depending
on what options you selected - potentially quite a while if you enabled the Ruby runtime
and selected a version to install.

.. code-block:: bash

	$ ./install.sh <path/to/production-pacemaker.yml>

.. WARNING::
	If you have chosen to install on a Micro instance, and installing a Ruby runtime,
	you'll quite likely exhaust the CPU allocation for that instance. This will make the
	server quite unresponsive for a period of time.

.. NOTE::
	Paasmaker is designed to run as a non-root user. The install script calls sudo
	where it needs to (and you'll see a password prompt if appropriate). Only use
	``sudo`` for commands when shown explicitly in this guide, otherwise files
	may be owned by root instead of the correct user.

	You may also ask how Paasmaker's routers can listen for HTTP requests on
	port 80 whilst not running as a root user. The init script that the installer
	generates is set up to insert an iptables rule that redirects port 80 transparently
	through to port 42531, which the managed Nginx that runs as a non-root user listens on.
	You don't need to do this though - if you're using an Elastic Load balancer, you can
	just direct the traffic directly to port 42531.

Once the installation is complete, you can start up Paasmaker, and verify that it's
working.

.. code-block:: bash

	$ sudo /etc/init.d/paasmaker start

It will either report that it started successfully, or that it failed. If it failed,
you can check /var/log/paasmaker.log to see why it failed.

Alternately, you can start Paasmaker in debug mode, which will prevent it from
forking into the background. It also prints all log messages to the screen. This
can make it easier to figure out what it is doing on startup for initial installations.
To do this, make sure you're in the root of the Paasmaker git checkout.

.. code-block:: bash

	$ ./pm-server.py --debug=1
	... log output ...
	... press CTRL+C to quit ...

Pointing to the database
------------------------

The default configuration uses an SQLlite database on the local filesystem. For our
setup, we want the data to be stored in our RDS instance. You'll need to edit the
``paasmaker.yml`` file to set this up.

The database configuration is supplied as a `SQLalchemy DSN
<http://docs.sqlalchemy.org/en/rel_0_8/core/engines.html#database-urls>`_. For our case,
the DSN looks like this::

	postgresql://pacemaker:password@127.0.0.1/pacemaker

Or like this if you're using MySQL::

	mysql://pacemaker:password@127.0.0.1/pacemaker

In ``paasmaker.yml``, find the ``dsn:`` option and update it appropriately.

.. code-block:: bash

	$ vim paasmaker.yml
	...
	  dsn: postgresql://pacemaker:password@127.0.0.1/pacemaker

Once you've saved the file, restart Paasmaker. It will then recreate the tables on
the server, or exit with an error if it can not connect to the database for any reason.
It may take a while to restart (5-10 seconds) whilst it recreates the tables.

.. code-block:: bash

	$ sudo /etc/init.d/paasmaker restart
	... be patient whilst it creates the tables ...

Bootstrapping the Pacemaker
---------------------------

At this stage, the Pacemaker is running, but it has no users, so you can't log into
the system. You should create the initial user, and a role that permits them to log
in and work with the system.

When the installer wrote out the ``paasmaker.yml`` file, it chose a super token for
you, to authenticate with. However, super token authentication isn't allowed by
default for security reasons. You'll need to edit the ``paasmaker.yml`` file to allow
super tokens for the next step. Whilst you're in the file, make a note of the super
token as well for the next step.

.. code-block:: bash

	$ vim paasmaker.yml
	...
	  super_token: 12345678-90ab-cdef-1234-567890abcdef
	  # You're adding allow_supertoken.
	  allow_supertoken: true
	...
	$ sudo /etc/init.d/paasmaker restart

Paasmaker ships with a shell script that can set up a new database for you. You
just need to run it with the right parameters and it will set everything up for you.

.. code-block:: bash

	$ ./new-database.sh
	Usage: ./new-database.sh username email fullname password superkey
	$ ./new-database.sh freefoote freefoote@paasmaker.org "Daniel Foote" \
	"securepassword" "<super_token value from paasmaker.yml>"
	... output as it executes the API commands ...

Then, you can access the Pacemaker via the DNS name you gave it, and the TCP port
42500. For example, http://pacemaker.paasmaker.net:42500. You should be able to
log in and navigate around the control panel. You won't be able to deploy
applications yet, as there are no heart nodes to run them and no routers to route
to them.

.. NOTE::
	You should only contact the Pacemaker directly for testing and debugging.
	Normally, you should go through the router normally, which gives you request
	logging and auditing. However, at this stage of the setup, we don't have a
	router component set up for it to use.

Under the hood, the ``new-database.sh`` script looks like this:

.. code-block:: bash

	#!/bin/bash

	USERNAME="$1"
	EMAIL="$2"
	NAME="$3"
	PASSWORD="$4"
	SUPERKEY="$5"

	if [ "$5" == "" ];
	then
		echo "Usage: $0 username email fullname password superkey"
		exit 1
	fi

	./pm-command.py user-create $USERNAME $EMAIL "$NAME" $PASSWORD --key=$SUPERKEY
	./pm-command.py role-create Administrator ALL --key=$SUPERKEY
	./pm-command.py workspace-create Example example {} --key=$SUPERKEY
	./pm-command.py role-allocate 1 1 --key=$SUPERKEY

The script makes a few assumptions about the database IDs of the new user, role,
and workspace it will create. Otherwise, it just uses the command line tools to
interact with the Pacemaker node. The command line tools actually use the HTTP
API to talk to the pacemaker.

Changing the installation
-------------------------

If you want to change the installation, you can in many cases update your installation
yaml file and re-run the installation script. The installation script will only perform
updates that haven't already been done, although at this time does not support uninstalling
things.

The installation script will also read in the ``paasmaker.yml`` file, and update it
as appropriate. It will merge in your changes to the file with the installation instructions
as best as it can, although this process removes any comments from the file.

The heart and router
--------------------

In this deployment, another server runs both the heart and router components. The
design is so that there can be multiple heart/router nodes in the system to handle
higher demands.

For simplicity, we run both hearts and routers together. In a larger setup, it would
likely be seperated into a set of router nodes and a set of heart nodes.

For a little more elasticity, we are using instance storage for these instances.
Once the node has been installed and configured correctly, we snapshot it and
bundle it into an AMI, so we can start up new nodes quickly later.

To kick this off, start up a brand new instance, but this time use an instance
store instead. Use Ubuntu 12.04 again.

The settings used:

* Ubuntu 12.04 instance store AMI.
* m1.small instance class.
* Name - I called mine "Production - Heart/Router". You should give yours something
  meaningful for your setup.
* Key pair - choose an appropriate key pair.
* Security group - use the Paasmaker group you created previously.

Once it starts, you can update the packages and also get the server up to your
standard operating environment.

Then we can install Paasmaker:

.. code-block:: bash

	$ sudo apt-get install git
	$ git clone git@bitbucket.org:paasmaker/paasmaker.git

Now we need to create a configuration file for this install. You can base it off
the one in install/config/example-production-heart.yml. It is reproduced here
to explain its entries:

.. code-block:: yaml

	is_heart: true
	is_router: true
	is_pacemaker: false

	master_node: production.paasmaker.net
	master_port: 42500
	# Replace node_token with your node token.
	node_token: 12345678-90ab-cdef-1234-567890abcdef
	redis_mode: defer-to-master

	shutdown_daemons_on_exit: false

	install_init_script: true
	enable_init_script: true
	init_redirect_port80: true

	runtime_php_enable: true
	runtime_php_disable_system_apache: true

	runtime_rbenv_enable: true
	runtime_rbenv_versions: ['1.9.3-p327']

	service_managedredis_enable: false
	service_managedpostgres_enable: false
	service_managedmysql_enable: false

	write_paasmaker_configuration: true

A very important part of this is the node token inserted above. When the install
script ran on the Pacemaker, it generated a new node token. Each node in the cluster
should have the same node token, as that is how they authenticate with each other.
The design of Paasmaker is such that any node registers with the Pacemaker, and then
the Pacemaker can send applications to the node after that. To do this, each node
needs to know three things; the pacemaker hostname and port, and the node token.

You can fetch the node token from the pacemaker node:

.. code-block:: yaml

	pacemaker$ cd paasmaker
	pacemaker$ grep node paasmaker.yml
	node_token: 12345678-90ab-cdef-1234-567890abcdef

Another important part of the configuration is how Redis is configured. In the
installation configuration, you'll see the directive ``redis_mode: defer-to-master``.
What this means is that when it needs the Jobs redis, it will connect directly
to the Redis that the pacemaker node manages. The same applies for the stats redis.
The routing table redis is slightly different though. Paasmaker will instead start
a local Redis for the local router, and then configure that local Redis to be a slave
of the master router table Redis located on the Pacemaker node. This is for two reasons;
speed and redundancy. It's faster to access the local Redis, and also, if the master
goes away for a while, the router will continue to route with the last known routing table.
Redis handles retrying the connection to the master and resyncrhonising the table when
the master becomes available again.

Also note that the heart/router node has no need to connect to the Pacemaker SQL database.

Now you can start the installation script:

.. code-block:: bash

	$ ./install.py example-production-heart.yml
	... and wait whilst it installs everything ...

Once it is installed, you can start it up, and make sure that it started correctly.
It should immediately register with the master node, and appear in the list of
nodes on the Pacemaker.

.. code-block:: bash

	$ sudo /etc/init.d/paasmaker start

Also, you might like to check that the node correctly set up the slave Redis table.
You can use ``redis-cli`` to check this. If it already has keys in it, that means
that it's replicated the routing table from the master. If it is empty, then it has
not been able to replicate. Please note that the ``redis-cli`` path may change in
future as we use different versions of Redis by default.

.. code-block:: bash

	$ thirdparty/redis-2.6.9/src/redis-cli -p 42510
	redis> keys *
	1) "serial"
	2) "instances:pacemaker.production.paasmaker.net"
	3) "instance_ids:pacemaker.production.paasmaker.net"

Finally, check that the router is listening on Port 80. You can check this by telnetting
to the port:

.. code-block:: bash

	$ telnet localhost 80
	Trying 127.0.0.1...
	Connected to localhost.
	Escape character is '^]'.
	^]q

	telnet> q
	Connection closed.

(You can hit CTRL+] to bring up the telnet menu, and then type q and enter to quit.)

.. NOTE::
	Remember that Paasmaker runs as a non-root user. To make this work, the init
	script inserts iptables rules to redirect port 80 to port 42531.

Now, you can put this new heart node into the rotation for the Elastic Load Balancer,
as we have a router that can now handle this. Assuming your DNS is all configured,
you can now visit the fully routed hostname for the Pacemaker. In our setup,
this is http://pacemaker.production.paasmaker.net/.

If you log in again, and go to the overview page, you'll see a series of requests to
the pacemaker, and you should see streaming updates - around 5 requests/second - to
the pacemaker. These are the `socket.io <http://socket.io>`_ updates streaming
back to your browser via the load balancer. (Because the Elastic Load balancer,
and at time of writing, our nginx router, does not support web sockets, it is using
a series of XHR long poll requests to get realtime updates).

.. NOTE::
	When a node registers with the master, it sends along a route to get back
	to that node. The master checks this before accepting the registration. By default,
	a node attempts to send it's FQDN. Sometimes this autodetection does not work
	very well, and in the case of nodes on EC2, it returns an internal hostname
	only. In future, we plan to support scenarios where the Pacemaker node is
	outside of EC2, whilst execution nodes are inside EC2, which currently won't
	work correctly unless you manually set the ``my_route`` option in ``paasmaker.yml``
	on each individual node.

Deploying your first application
--------------------------------

As a test, you can deploy the example paasmaker-tornado-advanced application
to make sure that the system is working correctly. To do this, you can create
a new application in the control panel, pointing it to the git URL for that
application:

.. code-block:: bash

	git@bitbucket.org:paasmaker/paasmaker-python-simple.git

Once you've created the application, you should be able to start it and then
visit it via the URLs provided by the control panel. When you're done, you
can stop the application, and then delete it via the control panel.

Protecting the Pacemaker with SSL
---------------------------------

Commonly, you would want to protect access to the Pacemaker (and thus the
web console) with SSL, to protect passwords in transit. There are many ways
to do this, but for purposes of this discussion, the flow looks like this:

* The Elastic Load Balancer is configured to terminate the SSL, and the
  certificate is uploaded to that.
* The Elastic Load Balancer forwards decrypted sessions through to port
  42532 on the routers. The routers are configured to assume that connections
  on this port are decrypted SSL sessions and they pass along headers to
  the applications (X-Forwarded-Scheme: https) to let them know.
* The router then forwards the request to the Pacemaker.

.. NOTE::
	Be sure to add 42532 to your security group, to allow the Elastic
	Load Balancer to be able to talk to it.

You should then ensure that the Pacemaker gets requests on SSL. In the
Pacemaker section of the configuration file, on the Pacemaker node only,
you can set ``require_ssl`` to true, like so:

.. code-block:: yaml

	pacemaker:
	  require_ssl: true

And then the Pacemaker will redirect to the SSL version of the page as required.
If you try to perform API requests against it without SSL turned on, they
will be denied.

Currently, we don't have a way to configure the Nginx components of the routers
to decrypt SSL; we plan to add this in the future. However, Paasmaker nodes
can be configured to do SSL themselves, although this means you'll then
need to access them directly, rather than through the router. To turn this
on, in your ``paasmaker.yml`` file:

.. code-block:: yaml

	https_port: 42501
	ssl_options:
	  certfile: /path/to/server.crt
	  keyfile: /path/to/server.key

Resetting a node
----------------

Nodes other than a Pacemaker store all working data inside a subdirectory
called ``scratch``. The idea behind this is that you can easily reset a node
by removing the contents of this directory. Pacemaker nodes additionally store
data in the configured SQL database, which you will need to drop all tables
in to reset Paasmaker.

But it's not quite that simple. Paasmaker is designed to be agressive with
keeping things running. In the default production configuration, when you
stop the Paasmaker service (via ``/etc/init.d/paasmaker stop``) it only
shuts down the Python paasmaker component. It will leave any managed Redis
instances, Nginx instances, and applications running. (It does take the
applications that it manages out of the routing table, however, and the
Pacemaker is notified that these are stopped so it can take action to
heal the system). It does this for a few reasons; the first being to allow
you to restart the Python management component without disruption to the system,
and the second being a safeguard in case Paasmaker crashes for any reason.

For development, all managed services have a flag, called ``shutdown``, that
when set to true will get Paasmaker to shut down any associated daemons
and applications, with the risk of losing a little bit of application traffic
due to the order of execution of the instructions. This mode is not designed
for production.

So, to reset a production node, you will need to take one of two approaches:

* Stop the Paasmaker service (``sudo /etc/init.d/paasmaker stop``), remove
  the scratch directory, (``rm -rf paasmaker/scratch``), and then reboot the
  server.
* Stop the Paasmaker service (``sudo /etc/init.d/paasmaker stop``), locate any
  redis-server processes that it launched (which should be obvious from the
  command line), locate any nginx processes that it launched (if the node is
  a router), and any applications that it was managing (which you can find
  if you look for ``pm-supervisor.py`` processes). Once you kill all of these
  processes, Paasmaker is completely stopped.

Server Monitoring
-----------------

Don't forget to install the appropriate hooks onto the server for your server
monitoring system. Currently, we are using `CopperEgg <http://copperegg.com>`_
for monitoring the production servers, to save us having to run our own monitoring
system, such as Zabbix or Nagios.

Backups
-------

There are several components you will want to back up. Paasmaker can store a lot
of data; but only some of it is critical to restoring the Pacemaker node.

Only your Pacemaker nodes need to be backed up. Hearts and Routers should be able
to be rebuilt from scratch, and the Pacemaker will then distribute out work to them
as they come back online.

.. WARNING::
	Restoring a Pacemaker node from a backup has not been tested and documented
	at this time. These are general notes about what to backup that should be able
	to result in a successful restore in the future.

* ``paasmaker.yml``. This is the configuration file. If you've made customisations
  to it, you'll want to back it up.

* Backup the database. If you're running on a standalone box, you might find the
  ``automysqlbackup`` and ``autopostgresqlbackup`` packages useful. In our case,
  I just used these instructions to create backup files of the RDS instance (for
  the application databases):

  .. code-block:: bash

  	$ sudo apt-get install automysqlbackup
  	$ sudo vim /etc/default/automysqlbackup
  	...
  	DBHOST=your-rds-hostname.ap-southeast-2.rds.amazonaws.com
	USERNAME=root
	PASSWORD=yourpassword
	...
	DBNAMES=`mysql --defaults-file=/etc/mysql/debian.cnf --execute="SHOW DATABASES" \
	-h your-rds-hostname.ap-southeast-2.rds.amazonaws.com -u root \
	--password=yourpassword | awk '{print $1}' | grep -v ^Database$ | \
	grep -v ^mysql$ | tr \\\r\\\n ,\ `

  Note that unfortunately you need to give the username, password, and host twice due
  to how the script works.

  You can test it with:

  .. code-block:: bash

  	$ sudo automysqlbackup

  And then check for files in ``/var/lib/automysqlbackup``.

  If you've followed my instructions exactly, install the ``autopostgresqlbackup``
  package, and you'll automatically have Postgres backups appear in ``/var/lib/autopostgresqlbackup``.

  .. code-block:: bash

  	$ sudo apt-get install autopostgresqlbackup
  	$ sudo autopostgresqlbackup
  	$ ls /var/lib/autopostgresqlbackup

  If you're using the default sqlite database, you can fetch the database file from
  the ``scratch/`` directory and back that up.

* ``scratch/UUID``. For simplicity, Paasmaker writes it's UUID to this file. If you
  backup and restore this file, it will speed up bootstrapping the replacement server.

* Redis instances. As you've seen, Paasmaker uses three Redis instances to store data.
  Which ones you backup depends on how much data you want to store.

  .. WARNING::
  	These instructions use a `synchronous save <http://redis.io/commands/save>`_ command
  	on the Redis instances. This causes any queries on that Redis instance to block.
  	This may cause Paasmaker nodes to hang for a few moments whilst this is completed.
  	A synchronous save was chosen for these instructions so when you copy off the database
  	file, you can be sure that the save has completed.

  * The routing table master Redis. This contains the current routing table. Assuming that
    only the Pacemaker has completely failed, and the rest of the system is still active
    and unchanged, then the contents of this Redis still apply. This proceedure will generate
    a safe backup:

    .. code-block:: bash

      $ cd paasmaker
      $ thirdparty/redis-2.6.9/src/redis-cli -p 42510 SAVE
      $ tar -czvf table-backup.tar.gz scratch/redis/table

  * The stats Redis. This contains the traffic stats. You'll probably want to back this up
    to keep this historical data. This proceedure will generate a safe backup:

    .. code-block:: bash

      $ cd paasmaker
      $ thirdparty/redis-2.6.9/src/redis-cli -p 42512 SAVE
      $ tar -czvf stats-backup.tar.gz scratch/redis/stats

  * The jobs Redis. The contents of this Redis instance are transactional, and Paasmaker
    doesn't mind losing the contents of this. Any jobs that were in progress will be
    aborted, but the final say for the state of the system is the SQL database, so the jobs
    Redis can be lost if needed. Also, due to the size of the data, Paasmaker is already
    going to be removing old jobs periodically. You might not want to back this up as it
    can get quite large quickly.

    If you must back this up, use this proceedure:

    .. code-block:: bash

      $ cd paasmaker
      $ thirdparty/redis-2.6.9/src/redis-cli -p 42513 SAVE
      $ tar -czvf jobs-backup.tar.gz scratch/redis/jobs

* Prepared applications. Prepared applications are stored in ``scratch/packed/``. If you
  just back up the contents of that directory, Paasmaker will be able to redeploy applications
  again quickly.

Changing security credentials
-----------------------------

If you have an incident where you no longer trust the node token, you can easily change it.
To change it, first update the node token on the Pacemaker node, and then go through each
heart and update it and restart them.

Whilst the node token doesn't match, heart nodes will be unable to report in. If a node doesn't
report in for 90 seconds, it is assumed to be down and will have its instances replaced elsewhere.
Please keep that in mind when updating nodes.

Bundling into an AMI
--------------------

TODO: Write this section.
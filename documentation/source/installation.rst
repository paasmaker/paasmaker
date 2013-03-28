
Installing Paasmaker
====================

Paasmaker is currently supported on the following platforms:

* Ubuntu 12.04 and 12.10.
* OSX 10.8 (development only)

.. NOTE::
	This installation document is for a single node development Paasmaker
	that runs on your machine only. See the :doc:`administrator manual <administrator>`
	for how to install larger multi-node setups.

Generic Notes
-------------

Paasmaker ships with it's own Python script that will install all the components
required to make Paasmaker work. This script itself takes a yaml file as an input
that tells it what to install for you.

Paasmaker comes with a few example installation configuration files to get you
started. Have a look in ``install/configs/`` to see them.

Paasmaker attempts to make the least number of changes to your system as possible,
to play nicer with other things that might already be installed on the system. Also,
this allows you to remove it easily.

The install script will install some system packages based on your configuration,
but it attempts to install only packages that will play well with other things
already installed on your system. Anything that might not play well, or requires
specific versions, is installed into the same directory that Paasmaker came from.

At this time, you will need to clone the git repository to install Paasmaker.

The installation script is designed to be re-run to update your environment
if you want to make changes later. It will skip anything that it has already
done and just update other things. This can be used to enable other runtimes
at a later stage, or add new versions to existing runtimes (such as the Ruby
runtime).

.. NOTE::
	The Ruby runtime is not installed and enabled by default. The Ruby runtime
	uses rbenv and ruby-build, and compiling Ruby can take quite some time. You
	can easily copy the configuration and enable this, and re-run the installation
	script to get this set up for you.

.. NOTE::
	You will note that the installation script does a lot of what some other
	devops management systems (such as Opscode's Chef) does. For the moment,
	we decided to reduce the external dependencies and write our own script.
	However, because the install script takes in yaml configuration files,
	you could easily wrap this in a Chef recipe. In the future, we plan to
	offer native Chef recipies to install Paasmaker.

What does the installer do?
---------------------------

The installer does the following things:

* Installs any Python dependencies into a seperate virtualenv (so as not to interfere
  with anything else installed on the system).
* Installs a few system packages that are required - mostly development libraries, and
  wget, curl, and zip.
* Installs `Redis <http://redis.io>`_ from source into a local directory (not a system
  install). We require a version newer than is distributed with Ubuntu.
* Installs `OpenResty <http://openresty.org>`_ from source into a local directory. OpenResty
  is a patched distribution of Nginx - the router component requires the patches to work.
* Installs your system's MySQL and Postgres packages (if you have those services enabled
  in the configuration file that you feed the install script).
* Install Apache and PHP (on Ubuntu) but does not configure them. Paasmaker starts it's
  own version of Apache as needed. On OSX, it uses the already-installed Apache and PHP.
* Install `rbenv <https://github.com/sstephenson/rbenv/>`_ for Ruby support, and installs
  one or more versions of Ruby (if enabled in your configuration).
* If configured, writes out an init script to start Paasmaker on boot. It can also enable
  this script. This is only supported on Linux.

Installing on OS X
------------------

To install on OSX, you will need a few things set up first:

1. The command line development tools from Apple. You can either download and
   install these from `http://connect.apple.com <http://connect.apple.com>`_
   (you will need a developer Apple ID, but these are free), or you can install
   X-Code via the App Store, and then install the command line tools addon.

2. Install homebrew if you don't already have it. You can install it from
   `the homebrew site <http://mxcl.github.com/homebrew/>`_.

3. Install pip. OSX ships with an appropriate version of Python, but does not
   come with pip. The easiest and least-modification way to install this is
   by running the following in a terminal:

   .. code-block:: bash

   		$ sudo easy_install pip

Now, you can jump to the installing on Ubuntu instructions - as the process
to install is virtually identical once you have the right tools installed.

.. NOTE::
	OSX is not going to be a supported platform for production. It is only
	indended for working on Paasmaker and developing applications with Paasmaker.

Installing on Ubuntu
--------------------

We are assuming you are on Ubuntu 12.04 or greater. Also, we assume that you have
git installed. If not, you will need to run ``sudo apt-get install git-core``.

First, clone the repository:

.. code-block:: bash

	$ git clone git@bitbucket.org:paasmaker/paasmaker.git

Now, in this example we're going to use the 'example-hacking' configuration,
which is designed to set up the system as if you were going to modify the Paasmaker code.
You may be asked for your sudo password during this process, to install a few
system packages.

.. NOTE::
	The installation process can take a while. It should be about 20 minutes on an
	average internet connection. It also does compile some components which may take
	more or less time depending on your machine.

.. code-block:: bash

	$ cd paasmaker
	$ ./install.py install/configs/example-paasmaker-hacking.yml

Alternately, you can copy that configuration file, and alter it to match
what you would like, and then run the installation script against that file.

.. note::
	Did the installer fail? It still has some rough edges, and we're working
	to improve it. It's safe to re-run until it completes successfully and will
	only make the changes it hasn't already made.

Once it's installed, you can start it up with the following command:

.. code-block:: bash

	$ ./pm-server.py --debug=1

If it fails to start, check the common problems checklist below.

You can then visit `http://pacemaker.local.paasmaker.net:42530/ <http://pacemaker.local.paasmaker.net:42530/>`_
in your web browser. If you used the example-paasmaker-hacking.yml file, Paasmaker
would have automatically created a user for you to log in with - use username ``paasmaker``
and password ``paasmaker``.

.. NOTE::
	The DNS name ``local.paasmaker.net`` always resolves to both ``127.0.0.1``
	and ``::1``. It is also a wildcard, so ``pacemaker.local.paasmaker.net`` or
	``myapplication.local.paasmaker.net`` will also resolve to your machine. This is
	provided for convenience for testing.

.. NOTE::
	Note that the TCP port used is 42530. This means that you're accessing the Pacemaker
	controller via the router component. If you want to access the Pacemaker directly
	(for testing/debugging), use port 42500 instead.

If this is your first time with Paasmaker, move on to the :doc:`getting started guide
<user-gettingstarted>`.

.. WARNING::
	In the supplied configuration, when you stop Paasmaker, it will stop all
	managed services, applications, and the router. To start them up again,
	just start Paasmaker again. This configuration was chosen for development
	to clean up after itself once you're done experimenting.

	In production, Paasmaker does not shut things down to prevent any traffic loss
	during Paasmaker restarts.

Instant gratification
---------------------

For instant gratification, you can deploy from the following repositories to
get a sample application:

* Python: ``git@bitbucket.org:paasmaker/sample-python-simple.git``
* PHP: ``git@bitbucket.org:paasmaker/sample-php-simple.git``
* Node.js: ``git@bitbucket.org:paasmaker/sample-node-simple.git``
* Ruby: ``git@bitbucket.org:paasmaker/sample-ruby-simple.git`` (you need to install
  the Ruby runtime to get this one to work).

These examples do rely on Paasmaker being installed with the default configuration
in ``example-paasmaker-hacking.yml``.

None of these sample applications use the Paasmaker interfaces. To see more
information about using these languages on Paasmaker, see the :ref:`runtime integration
documentation <user-languages-entry>`.

Common Problems
---------------

Here are some common issues that people run into when installing and starting
Paasmaker:

* Apache fails to start. Characterized by a "CalledProcessError: Command apache2
  returned non-zero exit status 1". The output should be nearby to indicate what
  went wrong; typically it's one of two things; either a coding error in Paasmaker,
  or Apache has run out of a certain type of shared memory, and won't start.

* One of the Redis servers (ports 42510 through 42512) fails to start, or nginx
  (on 42530-42532) fails to start. Because Paasmaker chose high TCP ports, other
  applications running on your computer may have assumed these ports for outgoing
  connections. Culprits tend to be web browsers.

Configuring Paasmaker
---------------------

.. NOTE::
	This is a basic overview of how to configure Paasmaker. For full details,
	see the :doc:`administrator manual <administrator>`.

The installer will write out a file, called ``paasmaker.yml`` that contains
the settings for your Paasmaker installation. The most common thing that you'll
want to do is to add new plugins. Check the documentation for each plugin
to see how to add it to your installation.

Sharable links, or trying this out on EC2
-----------------------------------------

This installation guide results in a configuration that works on your machine
only. If you try to share links it gives you with other people, they won't work,
because all the DNS names resolve to localhost.

This also means that if you install this on a remote EC2 instance, the same
thing will happen - you won't be able to access applications.

There is a workaround you can use for testing purposes. Firstly, find the IP
address of the machine on an interface that you want to share. For example,
if you're using a remote EC2 instance, get the public hostname and resolve
that into an IP address.

Once you have that, you can set your cluster hostname to a `xip.io <http://xip.io>`_
resolved name. Then, all your links will work correctly.

Edit the installation configuration file, ``install/configs/example-paasmaker-hacking.yml``,
and update the ``cluster_hostname`` variable:

.. code-block:: yaml

	# In file install/configs/example-paasmaker-hacking.yml :
	...
	cluster_hostname: 10.0.0.1.xip.io
	...

And then re-run the installer:

.. code-block:: bash

	$ ./install.py install/configs/example-paasmaker-hacking.yml

When you restart your Paasmaker node, it will then be available via http://pacemaker.10.0.0.1.xip.io,
and any applications will be <application>.10.0.0.1.xip.io.

.. warning::
	Paasmaker currently doesn't support changing the ``cluster_hostname`` of an
	existing installation. If you change it, any new applications get the new name
	as they're inserted into the routing table, but old ones are not updated. We hope
	to have the pacemaker detect and fix this automatically in the future.

	A workaround is to stop and start all applications once you've changed the name.

.. note::
	We don't have an arrangement with the xip.io guys, and they provide an amazing
	free service! We hope to be able to provide our own service in the future for testing.
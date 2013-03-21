Ruby Support
============

Paasmaker is able to run Ruby applications. The default Ruby runtime plugin uses
`rbenv <https://github.com/sstephenson/rbenv/>`_ to support as many versions of Ruby
as you want to install.

To run web applications, generally the instance is supplied with a TCP port to listen
on. Traffic for that instance is then routed to that TCP port. If the application
crashes or fails, it will be restarted by the health manager. For performance,
you may like to use a performant Ruby environment such as `Thin <http://code.macournoyer.com/thin/>`_.

.. NOTE::
	If you used the :doc:`installation <installation>` guide to install Paasmaker,
	and used the ``example-paasmaker-hacking.yml`` install configuration, you won't
	have Ruby support enabled. This is because it can take some time to compile and
	install Ruby, so we've chosen to distribute with this option turned off.

	You can easily enable it in that file and re-run the installer again to install
	Ruby support. Note that this can take around an hour; compiling Ruby takes time.

	If you already have rbenv installed, Paasmaker will detect this if you use the
	``runtime_rbenv_for_user`` option set to true, and have installed rbenv in
	``~/.rbenv``.

.. NOTE::
	This note only applies if you have ``heart.shutdown_on_exit`` set to false, which
	is not the default configuration for development.

	If you use the Thin application server (as these instructions do), and have Paasmaker
	set up to not shutdown instances on exit (which is not the default configuration for
	development), and then stop Paasmaker with a SIGINT (which will happen when you hit CTRL+C
	if you're running it in debug mode), Thin will get this signal and then exit, which works
	outside the normal instance shutdown management flow.

	This can be annoying during development (with a non-standard configuration) if you restart
	your Paasmaker node a lot, as Paasmaker won't restart this instance automatically as it ends
	up in the wrong state. This is for the safety of the system. Once you've restarted your Paasmaker,
	you can stop and start the version to get the instance running ahead of the window when the health
	manager restarts it for you.

	If you stop Paasmaker by sending it a SIGTERM, as normal, the instances will continue to
	run in the background as normal.

	This is not an issue in production systems unless you manually run your nodes in debug
	mode and stop them with CTRL+C.

Integrating with common Frameworks and CMSs
-------------------------------------------

The guides below show how to integrate Paasmaker with some common Ruby frameworks
and CMS systems, including pitfalls for them.

.. toctree::
   :maxdepth: 2

   user-howto-ruby-rails
   user-howto-ruby-redmine

Integrating with any Ruby project
---------------------------------

If you're using your own Ruby framework, or a framework not documented, you should
be able to integrate Paasmaker easily into that system.

Assuming you're using bundler, add the following to your Gemfile:

.. code-block:: ruby

	gem "paasmaker-interface"

Then, in your application code, you can do the following:

.. code-block:: ruby

	require 'paasmaker'
	interface = Paasmaker::Interface.new([])

	service_credentials = interface.get_service('service-name')
	database_name = service_credentials['database']

	interface.is_on_paasmaker()

If you're developing outside Paasmaker, the Interface constructor
takes a list of override configuration files. For example, you
might instead do this:

.. code-block:: ruby

	require 'paasmaker'
	interface = Paasmaker::Interface.new(['development.yml'])

	service_credentials = interface.get_service('service-name')
	database_name = service_credentials['database']

	interface.is_on_paasmaker()

And then have the following ``development.yml`` file.

.. code-block:: yaml

	services:
	  mysqldb:
	    hostname: localhost
	    username: root
	    password: ''
	    port: 3306
	    database: yourdatabasename

	application:
	  name: test
	  version: 1
	  workspace: Test
	  workspace_stub: test

The example above will have a service called ``mysqldb`` that you
can point to whatever development database you would like.
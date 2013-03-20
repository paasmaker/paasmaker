Ruby Support
============

Paasmaker is able to run Ruby applications. The default Ruby runtime plugin uses
`rbenv <https://github.com/sstephenson/rbenv/>`_ to support as many versions of Ruby
as you want to install.

To run web applications, generally the instance is supplied with a TCP port to listen
on. Traffic for that instance is then routed to that TCP port. If the application
crashes or fails, it will be restarted by the health manager. For performance,
you may like to use a performant Ruby environment such as `Thin <http://code.macournoyer.com/thin/>`_.

.. WARNING::
	If you used the :doc:`installation <installation>` guide to install Paasmaker,
	and used the ``example-paasmaker-hacking.yml`` install configuration, you won't
	have Ruby support enabled. This is because it can take some time to compile and
	install Ruby, so we've chosen to distribute with this option turned off.

	You can easily enable it in that file and re-run the installer again to install
	Ruby support. Note that this can take around an hour; compiling Ruby takes time.

	If you already have rbenv installed, Paasmaker will detect this if you use the
	``runtime_rbenv_for_user`` option set to true, and have installed rbenv in
	``~/.rbenv``.

.. WARNING::
	There is currently an issue with Paasmaker if you're using the Thin application
	server with your Ruby applications, as suggested by these documents. When the Paasmaker
	node shuts down, Thin gets a signal and decides to shut down. Paasmaker specifically
	tries to shield instances from these signals (and it works in other languages) but
	something about Thin causes it to shut down.

	If you are able to debug this or offer a solution, please let us know.

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
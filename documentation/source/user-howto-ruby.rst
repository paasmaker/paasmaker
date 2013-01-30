Ruby Support
============

Paasmaker is able to run Ruby applications. The default Ruby runtime plugin uses
`rbenv <https://github.com/sstephenson/rbenv/>`_ to support as many versions of Ruby
as you want to install.

To run web applications, generally the instance is supplied with a TCP port to listen
on. Traffic for that instance is then routed to that TCP port. If the application
crashes or fails, it will be restarted by the health manager. For performance,
you may like to use a performant Ruby environment such as `Thin <http://code.macournoyer.com/thin/>`_.

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
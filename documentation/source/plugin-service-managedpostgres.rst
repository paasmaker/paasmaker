Managed PostgreSQL service
==========================

This plugin operates the same as the :doc:`plugin-service-postgres` plugin,
except that rather than using an external Postgres server, it starts it's own
Postgres server (seperate to any system one) and then grants databases on that
Postgres server.

.. note::
	It is intended for testing and development on a single machine, and saves
	the user from having to set up their own local Postgres installation.

For convenience, if you register this with the name ``paasmaker.service.postgres``
then your application manifests should in theory work in local development
and production automatically.

Note that Postgres runs as the same user that Paasmaker runs as, so this is
not a secure arrangement for application hosting. In the default plugin
configuration, the Postgres will only listen on localhost.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.managedpostgres.ManagedPostgresService
	  name: paasmaker.service.postgres
	  parameters:
	    root_password: paasmaker
	  title: Managed Postgres Service

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.managedpostgres.ManagedPostgresServiceConfigurationSchema

	The plugin has the following configuration options:
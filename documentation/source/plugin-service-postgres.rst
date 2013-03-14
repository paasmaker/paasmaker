PostgreSQL service
==================

This service plugin is designed to create a new user, database, and
password for each requested service. This is then a sandbox for an
application to store it's data.

No limits are placed on what the application is able to do in this database,
however, they can not exit their database.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.postgres.PostgresService
	  name: paasmaker.service.postgres
	  title: Postgres Service
	  parameters:
	    hostname: <hostname or IP of Postgres server>
	    port: 5432
	    username: postgres
	    password: your-postgres-password

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.postgres.PostgresServiceConfigurationSchema

	The plugin has the following configuration options:
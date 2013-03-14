MySQL service
=============

This service plugin is designed to create a new user, database, and
password for each requested service. This is then a sandbox for an
application to store it's data.

No limits are placed on what the application is able to do in this database,
however, they can not exit their database.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.mysql.MySQLService
	  name: paasmaker.service.mysql
	  title: MySQL Service
	  parameters:
	    hostname: <hostname or IP of MySQL server>
	    port: 3306
	    username: root
	    password: your-root-password

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.mysql.MySQLServiceConfigurationSchema

	The plugin has the following configuration options:
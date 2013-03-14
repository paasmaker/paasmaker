Managed Redis service
=====================

Redis is a little bit unique in that it's not easy to generate seperate databases
inside a single Redis instance. A typical practise is to start seperate Redis
instances for each application.

This plugin manages a set of Redis instances for you on the requesting host,
supplying the credentials to applications to each instance created. When the
service is deleted, the Redis instance is stopped and destroyed.

It will use the same version of Redis that Paasmaker installs for it's own use,
which is currently 2.6.9.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.managedredis.ManagedRedisService
	  name: paasmaker.service.managedredis
	  title: Managed Redis Service

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.managedredis.ManagedRedisServiceConfigurationSchema

	The plugin has the following configuration options:
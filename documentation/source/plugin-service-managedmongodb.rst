Managed Mongodb service
=======================

This plugin manages a set of Mongodb instances for you on the requesting host,
supplying the credentials to applications to each instance created. When the
service is deleted, the Mongo instance is stopped and destroyed.

This will currently use the packaged version of MongoDB, which may be an older
version.

This plugin is not intended for production use at this time, as it turns off some
features of MongoDB to speed up startup time.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.managedmongodb.ManagedMongoService
	  name: paasmaker.service.managedmongodb
	  title: Managed Mongodb Service

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.managedmongodb.ManagedMongoServiceConfigurationSchema

	The plugin has the following configuration options:
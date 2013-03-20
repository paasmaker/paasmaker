Managed MySQL service
=====================

This plugin operates the same as the :doc:`plugin-service-mysql` plugin,
except that rather than using an external MySQL server, it starts it's own
MySQL server (seperate to any system one) and then grants databases on that
MySQL server.

.. note::
	It is intended for testing and development on a single machine, and saves
	the user from having to set up their own local MySQL installation.

For convenience, if you register this with the name ``paasmaker.service.mysql``
then your application manifests should in theory work in local development
and production automatically.

Note that MySQL runs as the same user that Paasmaker runs as, so this is
not a secure arrangement for application hosting. In the default plugin
configuration, the MySQL will only listen on localhost.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.managedmysql.ManagedMySQLService
	  name: paasmaker.service.mysql
	  parameters:
	    root_password: paasmaker
	  title: Managed MySQL Service

.. warning::
	On Ubuntu, `AppArmor <https://wiki.ubuntu.com/AppArmor>`_ is
	configured by default to prevent mysqld from writing outside
	of ``/var``, which will prevent this service from starting.
	You will have to add Paasmaker's scratch directory to
	``/etc/apparmor.d/local/usr.sbin.mysqld`` like so:

	.. code-block:: none

		/path/to/paasmaker/scratch/ r,
		/path/to/paasmaker/scratch/** rwk,

	And then reload AppArmor:

	.. code-block:: bash

		$ sudo service apparmor reload

	The installer script will do this for you automatically
	on Ubuntu if you ask for the managed MySQL service. We
	plan to have this automatically patch other operating systems
	in the future.

Application Configuration
-------------------------

Applications can not currently pass any parameters to this service.

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.managedmysql.ManagedMySQLServiceConfigurationSchema

	The plugin has the following configuration options:

Configuring Paasmaker Plugins
=============================

Paasmaker ships with a series of plugins that give it additional functionality.
Some plugins can just be used as is with the default options, but for others
you will want to adjust the configuration.

The plugins are shown below, along with their configuration options and any
other notes for that plugin.

Runtime Plugins
---------------

.. toctree::
   :maxdepth: 2

   plugin-runtime-php
   plugin-runtime-shell

Authentication Plugins
----------------------

.. toctree::
   :maxdepth: 2

   plugin-auth-allowany
   plugin-auth-google

Plugin overview
---------------

Basically, to enable or configure a plugin, you need to add it to your
nodes ``paasmaker.yml`` file. In the file, you will have a section called
``plugins`` which has a list of plugins. To add new plugins, just add to
this list. For example:

.. code-block:: yaml

	plugins:
	- class: paasmaker.heart.runtime.PHPRuntime
	  name: paasmaker.runtime.php
	  parameters:
	    shutdown: true
	  title: PHP Runtime

``class`` is the full Python path to the class. ``name`` is the symbolic name
for the class, which in the case of runtimes and services (for example), will
match up with the names in your application manifest files. ``title`` is a friendly
title for the plugin, used in appropriate locations in the interface.

``parameters`` is a dictionary (possibly nested) of configuration for that plugin.
Each plugin's documentation will describe what values it takes and what the defaults
are. Parameters are the way that you configure plugins.

Using the same plugin twice
---------------------------

Paasmaker's plugin system has been designed to allow you to register the same plugin
multiple times with different symbolic names and configuration. This allows quite
a bit of control over your Paasmaker cluster.

For example, if you have two MySQL servers, and wanted to allow applications to choose
which one they belong on, you could register the MySQL plugin twice pointing to two
different servers.

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.mysql.MySQLService
	  name: paasmaker.service.mysql.server1
	  parameters:
	    hostname: server1.your-network.com
	    password: server1rootpassword
	    port: 3306
	    username: root
	  title: MySQL service (Server1)
	- class: paasmaker.pacemaker.service.mysql.MySQLService
	  name: paasmaker.service.mysql.server2
	  parameters:
	    hostname: server2.your-network.com
	    password: server2rootpassword
	    port: 3306
	    username: root
	  title: MySQL service (Server2)

Note that they each have a unique name. If you use the same name, the last plugin
with that name will be the actual registered plugin.

In the application manifests, you would specify either ``paasmaker.service.mysql.server1``
or ``paasmaker.service.mysql.server2`` as the service plugin to select between the
two servers.

Default plugins
---------------

Paasmaker will register you a set of default plugins, to save you specifying plugins
for all internal things. If you want to change the configuration of one of these
plugins, you can just redefine the plugin definition in your ``paasmaker.yml`` file
and this will take precedence over the default plugin.

Alternately, you can disable the default plugins altogether:

.. code-block:: yaml

	...
	default_plugins: false

However, if you do this, it's up to you to define all the plugins again. In the Paasmaker
source code, the file ``paasmaker/data/defaults/plugins.yml`` contains the default plugins.
There are a lot of default plugins, as the internal jobs are also plugins.
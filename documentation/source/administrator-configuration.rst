Configuring Paasmaker
=====================

Each node in the Paasmaker cluster has a configuration file,
typically called ``paasmaker.yml`` and located in the root
of Paasmaker's source code, that defines the options for that node.
The file is in Yaml format. This was chosen to make the file readable,
and to save creating a new configuration file format.

It is used to set up what roles this Paasmaker node has,
where to access all the resources that it needs, and what
plugins are configured for that node.

This document describes the options available for the file
and the general format of the file.

Format
------

A typical file has these major sections:

.. code-block:: yaml

	node_option: value
	node_option_2: value

	# The location of the master node.
	master:
	  host: localhost
	  port: 42500

	# Heart options, and if it's enabled.
	heart:
	  enabled: true
	  ... heart options ...

	# Pacemaker options, and if it's enabled.
	pacemaker:
	  enabled: true
	  ... pacemaker options ...

	# Router options, and if it's enabled.
	router:
	  enabled: true
	  ... router options ...

	# Additional plugins that this node has available,
	# and their configuration.
	plugins:
	- class: paasmaker.plugin.example.ExamplePlugin
	  name: paasmaker.plugin.name
	  title: Plugin Title
	  parameters:
	    option: value

	# Define how to connect to the various Redis
	# instances. The default is to have it all
	# managed on this node.
	redis:
	  jobs:
	    ... jobs connection details ...
	  stats:
	    ... stats connection details ...
	  table:
	    ... table connection details ...

If you omit the ``heart``, ``router``, or ``pacemaker`` sections, then it
is assumed that this is disabled for this node.

Many of the options have defaults, which the reference below shows if present.
If you are missing an option that is required, Paasmaker will not start up
and will give you an error indicating (mostly) what you need to set.

General Options
---------------

.. colanderdoc:: paasmaker.common.configuration.configuration.ConfigurationSchema

	The general options are:

The **redis** section's full definition looks like this:

.. code-block:: yaml

	redis:
	  jobs:
	    host: 0.0.0.0
	    managed: true
	    port: 42513
	    shutdown: false
	  stats:
	    host: 0.0.0.0
	    managed: true
	    port: 42512
	    shutdown: false
	  table:
	    host: 0.0.0.0
	    managed: true
	    port: 42510
	    shutdown: false
	  slaveof:
	    enabled: false
	    host: master-node
	    port: 42510

The **slaveof** section applies to the **table** Redis only.

.. colanderdoc:: paasmaker.common.configuration.configuration.MasterSchema

	The **master** section has these options:

.. colanderdoc:: paasmaker.common.configuration.configuration.PluginSchema

	Each plugin in the **plugins** list has the following options:

Pacemaker Options
-----------------

.. colanderdoc:: paasmaker.common.configuration.configuration.PacemakerSchema

	The pacemaker options are:

.. colanderdoc:: paasmaker.common.configuration.configuration.ScmListerSchema

	Each entry in the **scmlister** list has the following options. In your
	configuration, it might look like this:

	.. code-block:: yaml

		scmlisters:
		  - for: paasmaker.scm.git
		    plugins:
		      - paasmaker.scmlist.bitbucket

.. colanderdoc:: paasmaker.common.configuration.configuration.HealthCombinedSchema

	The **health** section has these options:

.. colanderdoc:: paasmaker.common.configuration.configuration.HealthGroupSchema

	Each **health** group has the following options:

The **health** section ends up looking like this:

.. code-block:: yaml

	pacemaker:
	  health:
	    enabled: true
	    use_default_checks: true
	    groups:
	      - name: default
	        title: Default Health Check
	        period: 60
	        plugins:
	          - plugin: paasmaker.health.downnodes
	            order: 10
	            parameters: {}
	          - plugin: paasmaker.health.adjustinstances
	            order: 20
	            parameters: {}
	          - plugin: paasmaker.health.stuckjobs
	            order: 20
	            parameters: {}

Heart Options
-----------------

.. colanderdoc:: paasmaker.common.configuration.configuration.HeartSchema

	The pacemaker options are:

Router Options
-----------------

.. colanderdoc:: paasmaker.common.configuration.configuration.RouterSchema

	The pacemaker options are:

.. colanderdoc:: paasmaker.common.configuration.configuration.NginxSchema

	For the **nginx** section, you can specify the following options:
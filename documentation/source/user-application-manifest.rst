Application Manifest Files
==========================

Paasmaker expects applications to have a manifest file, typically
called ``manifest.yml``, checked into the root of the files that
you upload. This file describes the application, it's settings,
how to run it, and any other information Paasmaker needs.

The idea is that this file is version controlled in your SCM
of choice, and provides a snapshot view of your application.

Manifest files can contain comments, as long as they meet
the `yaml specification for comments <http://www.yaml.org/spec/1.2/spec.html#id2780069>`_.
You can also use many Yaml features, however, the Yaml is loaded
with a safe parser that does not permit execution of custom
Python code embedded in the Yaml file.

A complete manifest file is shown below. After that is a description
of each section in detail.

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: tornado-simple
	  tags:
	    tag: value
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - echo "foo" > prepare.txt

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.shell
	      parameters:
	        launch_command: "python app.py --port=%(port)d"
	      version: 1
	    startup:
	      - plugin: paasmaker.startup.shell
	        parameters:
	          commands:
	            - echo "startup" > startup.txt
	    placement:
	      plugin: paasmaker.placement.default
	    hostnames:
	      - tornado-simple.local.paasmaker.net
	    crons:
	      - runspec: '* * * * *'
	        uri: /environ

	services:
	  - name: variables
	    plugin: paasmaker.service.parameters
	    parameters:
	      one: two

.. NOTE::
	Your manifest file does not have to be called ``manifest.yml``.
	Nor does it have to be in the root of your code. Nor are you
	limited to one manifest file per codebase. If the file name
	or path is different, you will need to specify the path to the
	manifest file when you submit your application to Paasmaker.
	You can see that option when you upload new applications.

	As an example, the Paasmaker repository has a ``documentation``
	directory at the top level, containing a manifest file. This
	manifest file is used to build and deploy the documentation.
	You can think of it as a tiny Paasmaker application inside
	a partially related codebase.

Manifest Format
---------------

.. code-block:: yaml

	manifest:
	  format: 1

This section is just to let Paasmaker know what format of manifest
file this application has. This is for future compatibility, as it
is likely that this format will evolve over time. This section is required.

Application
-----------

.. code-block:: yaml

	application:
	  name: tornado-simple
	  tags:
	    tag: value
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - echo "foo" > prepare.txt

This section describes the basic options for the application.
It supplies the name, any application specific tags, and what
steps are required to prepare the application.

Note that it does not specify what the version of the application
is; Paasmaker uses the name field to determine if it needs to
create a new application, or a new version of an existing application.

The runtime listed here is purely for running the prepare commands
with the correct version of the appropriate languge.
See :doc:`plugin-prepare-shell` for a detailed description of this.

The prepare commands is a list of plugins, so you can stack them
up. For example, you might use a Python PIP prepare plugin to fetch
dependencies, and then a shell plugin to build assets before packaging.

For example:

.. code-block:: yaml

	application:
	  ...
	  prepare:
	    ...
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - echo "foo" > prepare1.txt
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - echo "foo" > prepare2.txt

Instances
---------

.. code-block:: yaml

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.shell
	      parameters:
	        launch_command: "python app.py --port=%(port)d"
	      version: 1
	    startup:
	      - plugin: paasmaker.startup.shell
	        parameters:
	          commands:
	            - echo "startup" > startup.txt
	    placement:
	      plugin: paasmaker.placement.default
	    hostnames:
	      - tornado-simple.local.paasmaker.net
	      - *.tornado-simple.local.paasmaker.net
	    crons:
	      - runspec: '* * * * *'
	        uri: /environ

	  - name: admin
	    ...

The instance definition is the most complex part of the manifest
file, with the most options.

Your manifest can define multiple instance types, as long as they
have unique names. Each instance can have it's own runtime, startup
commands, cron tasks, and hostnames.

Let's deal with the major sections seperately.

**runtime**. This section defines what plugin will be used to
provide that language, and what version of that language that
you want. You also supply any runtime specific parameters. You
can look up the appropriate configuration for these in the
:doc:`user`.

**startup**. These are startup plugins. Paasmaker runs these
on the actual node that will execute your application, against
it's copy of the source tree, during startup. If these commands
fail, the instance will not start. Also, be aware that if you have
two instances, these commands will be run separately against both instances.
Also, if an instance fails and Paasmaker replaces it, the commands
will be run again against that new instance. The current working
directory for these commands is the instance root directory.

**placement**. This section defines what plugin to use to determine
where to place your application. It is intended that you can supply
tags which will cause your application instances to get placed on
certain servers with matching tags, but this has not yet been
implemented.

**hostnames**. This is a list of public hostnames that this instance
will respond to - but only when it's the active version of the application.
You can supply as many hostnames here as you would like. You can supply
a wildcard domain name, but for performance reasons, it will only
currently match one level. For example, ``*.foo.com`` will match ``www.foo.com``
but will not match ``bar.baz.foo.com``.

**crons**. This is a list of web cron tasks run against your instance.
You can supply a list of them along with a cron style string, and Paasmaker
will choose one of your instances at the appropriate times and request
that URL. Paasmaker does not go via the router, nor does it place a time
limit on these requests, and nor does it ensure that a previous run has
finished before starting the next run. Also note that cron tasks are only
run against the current version of the application; if there is no current
version, no cron tasks will be run. See below for all the options you can
configure for cron tasks.

.. colanderdoc:: paasmaker.common.application.configuration.Instance

	There are some other options not shown above. Here is the full schema
	for each instance:

.. colanderdoc:: paasmaker.common.application.configuration.Cron

	And for cron tasks, here are all the options available for them:

Services
--------

.. code-block:: yaml

	services:
	  - name: variables
	    plugin: paasmaker.service.parameters
	    parameters:
	      one: two

This section describes the services that your application uses. These are
defined by the plugins, and the parameters that you supply. What plugin
names are available to you is determined by the setup of the cluster that you
are running your application on.

For the parameters for each service, see the :doc:`user`.

You can specify as many services as your application needs. The application
will then be supplied those services with the names you specified.

The services are actually created when a new version of your application is
set up, so the services are available to any prepare tasks that you've supplied
in your manifest file. This can allow prepare tasks to alter data in databases,
for example.

Note that if one version of your application has only one service defined,
and a different version of the application has two versions defined, each version
of that application only sees what services it had specified in it's manifest file.

It is assumed that services with the same name retain the same data as new versions
are deployed. Paasmaker will never delete services during application creation.
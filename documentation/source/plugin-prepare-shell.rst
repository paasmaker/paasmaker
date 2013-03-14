Shell Prepare
=============

This plugin just runs shell commands against your source code tree
to prepare the application.

This plugin also serves as a shell startup plugin, with exactly the
same functionality.

Internally, it writes all the supplied commands into a shell script
and then executes that shell script. It aborts as soon as one of the
commands fails.

You can use the fact that it writes out a shell script to preserve some
environment variables between commands. However, once the script exits,
that environment is lost. This means if you have two seperate prepare
steps registered, they will not share an environment.

In your manifest file, you can place this code:

.. code-block:: yaml

	application:
	  ...
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - echo "foo" > prepare.txt
	            - BAR="foo"
	            - echo $BAR > prepare2.txt

The working directory for the commands is the root of the exported
code. There is nothing to prevent you from escaping this root at this
time (as Paasmaker currently expects that you trust your applications).

The commands also run in the context of the runtime specified in your
manifest. For example, if you have the following:

.. code-block:: yaml

	application:
	  ...
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.rbenv
	      version: 1.9.3-p327
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - ruby -v > ruby-version.txt

The file ``ruby-version.txt`` will contain
``ruby 1.9.3p327 (2012-11-10 revision 37606) [x86_64-linux]``. If you choose
a different version, then the version will match that string.

You can also use it during startup, although be aware that any environment
variables that you set are not passed along to the runtime. Also note that
the selected runtime will also be active for this stage as well with the
correct version to match.

.. code-block:: yaml

	instances:
	  - name: web
	    quantity: 1
	    ...
	    startup:
	      - plugin: paasmaker.startup.shell
	        parameters:
	          commands:
	            - echo "startup" > startup.txt

This plugin is enabled by default, as ``paasmaker.prepare.shell`` and
``paasmaker.startup.shell``.

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.pacemaker.prepare.shell.ShellPrepareParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

This plugin has no server configuration options.
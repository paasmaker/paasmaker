Python Support
==============

Paasmaker is written in Python, so you could then expect it to be able to run
applications written in Python. However, ironically, the Python language support
in Paasmaker is quite simple at this time.

To implement Python support, we use the :doc:`shell runtime plugin <plugin-runtime-shell>`
with an additional prepare plugin, and a few other minor quirks. This means that
the only version of Python available is the one on your system, and the Pacemaker
will not know what version of Python is available.

.. note::
	We hope to expand the Python support in the very near future.

Integrating with common Frameworks and CMSs
-------------------------------------------

We do not currently have any guides for specific frameworks or CMS systems.
If you use Paasmaker to deploy something, please let us know how you did it
so we can share it with others.

Integrating with any Python project
-----------------------------------

Here is an example guide on how to deploy a simple Python Tornado application
with Paasmaker, using a ``virtualenv`` for dependencies.

The complete example is in the `python-tornado-simple <https://bitbucket.org/paasmaker/paasmaker-tornado-simple/>`_
repository on BitBucket, but here are the key modifications to make this all work.

Firstly, you will need a ``requirements.txt`` file. List out the pip packages
that your application requires. And add a reference to ``pminterface`` as well.
You will likely already have one of these files for your project.

.. code-block:: none

	# In requirements.txt
	# Your packages:
	tornado

	# The Paasmaker interface:
	pminterface

In your manifest file, we set up the prepare plugin to use the :doc:`Python pip prepare
<plugin-prepare-pythonpip>` plugin. This will create a virtual env, and download the
packages in your ``requirements.txt``. The dependencies get packaged up for your application
before it goes off to be executed.

Here is the important section from a manifest file:

.. code-block:: yaml

	application:
	  name: tornado-simple
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.shell
	      version: 1
	    commands:
	      - plugin: paasmaker.prepare.pythonpip
	        parameters:
	          virtualenv_name: ENV

To run your application outside of Paasmaker, or if you add the directory in development
mode, you'll need to set up your virtualenv manually. This is basically what the plugin
does for you:

.. code-block:: bash

	$ virtualenv ENV
	$ . ENV/bin/activate
	$ pip install -r requirements.txt
	$ deactivate

Next, we modify the Python entry point to load the virtualenv directly, rather than having
to be started in the context of a virtualenv.

.. code-block:: python

	#!/usr/bin/env python

	# Built in imports
	import os
	import sys

	# See if the virtualenv is set up.
	if not os.path.exists("ENV/bin/pip"):
		print "virtualenv not installed. Make sure you've set up the virtualenv first."
		sys.exit(1)

	# Activate the environment now, inside this script.
	bootstrap_script = "ENV/bin/activate_this.py"
	execfile(bootstrap_script, dict(__file__=bootstrap_script))

	# Import anything only available via the virtualenv.
	import tornado

	# Now the rest of your normal code.

Now you can also access the Paasmaker interface. You might want to create one
global instance of it and then use that in your code later:

.. code-block:: python

	import pminterface
	interface = pminterface.PaasmakerInterface([])

	interface.is_on_paasmaker() # Returns True or False
	interface.get_service('named-service') # Returns a dict

In the tornado-simple application, see the ``InfoHandler`` for other things
you can do with the interface. If you've assigned a database, you will be able
to fetch the connection details from the interface for your application startup.

Finally, to start the application, we simply use the shell runtime, as shown
in this section of the manifest file:

.. code-block:: yaml

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.shell
	      parameters:
	        launch_command: "python app.py --port=%(port)d"
	      version: 1

In the example above, the TCP port it should use is given on the command line.
Alternately, you can get this in code by reading the ``PM_PORT`` environment
variable:

.. code-block:: python

	PORT = 8000

	# Read in the port from the environment, if present.
	if 'PM_PORT' in os.environ:
	        PORT = int(os.environ['PM_PORT'])

	# Or read from the interface:
	PORT = interface.get_port()

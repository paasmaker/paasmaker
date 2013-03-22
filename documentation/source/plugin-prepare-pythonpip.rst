Python PIP Prepare
==================

This plugin creates a virtualenv and installs the packages given by the
``requirements.txt`` file in your project.

It tries to be clever with package caching; if it has seen the ``requirements.txt``
file before, it instructs pip not to check the index and just to fetch
the packages from the cache, which does speed up redeploys somewhat.

The basic process it takes is this:

.. code-block:: bash

	$ virtualenv <environment name>
	$ . <environment name>/bin/activate
	$ pip install -r <requirements file name>
	$ virtualenv relocatable <environment name>

.. warning::
	This plugin is not heavily tested. Please let us know about your experiences
	with this plugin.

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.pacemaker.prepare.pythonpip.PythonPipPrepareParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

This plugin has no server configuration options.
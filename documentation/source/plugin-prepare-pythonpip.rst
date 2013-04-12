Python PIP Prepare
==================

This plugin creates a virtualenv and installs the packages given by the
``requirements.txt`` file in your project.

This plugin is very crude and only does just enough to speed up deployments
with PIP. It will create a checksum of your ``requirements.txt`` contents, and then
download and install packages into a persistent ``.pybundle`` file. This ``.pybundle``
file is re-used on subsequent deploys instead of fetching from the internet.

The basic process it takes is this:

.. code-block:: bash

	$ virtualenv <environment name>
	$ . <environment name>/bin/activate
	$ virtualenv relocatable <environment name>
	$ # If this is the first time we've seen this requirements.txt file:
	$ pip bundle /persistent/bundle/location -r <requirements file name>
	$ pip install /persistent/bundle/location

.. warning::
	This plugin is quite crude, and is the minimum to get you started. Please
	let us know how we can improve it.

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.pacemaker.prepare.pythonpip.PythonPipPrepareParametersSchema

	The plugin has the following runtime parameters:

Server Configuration
--------------------

This plugin has no server configuration options.
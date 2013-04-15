Node.js Support
===============

Paasmaker is able to run Node.js applications. The plugin that ships with Paasmaker
manages the installed versions of node.js with `nvm <https://github.com/creationix/nvm>`_.
By default, it will install Node.js v0.8.22. You can easily install other versions by
specifying them in the installation script.

Integrating with common systems
-------------------------------

The guides below show how to integrate Paasmaker with some common Node.js systems.

.. toctree::
   :maxdepth: 2

   user-howto-nodejs-nodecellar

Integrating with any Node.js project
------------------------------------

We supply an interface for Paasmaker for Node.js, which should make integration
quite simple.

Firstly, assuming you're using npm and a package.json file, you can add the following
to that file to get the interface:

.. code-block:: json

	{
	    ...
	    "dependencies": {
	        "paasmaker": ">=0.9.0"
	    },
	    ...
	}

Then, in your code, you can use the following to fetch Paasmaker metadata:

.. code-block:: javascript

	var paasmaker = require('paasmaker');
	var pm = new paasmaker(['override.json']);
	var credentials = pm.getService('servicename');

Several notes about the interface:

* The interface is syncrhonous, however, it only reads environment variables or
  files from the filesystem, so it should not significantly slow down your applications
  startup time.
* The call to ``getService()`` returns an object. The keys depend on the values
  provided by the service in question.
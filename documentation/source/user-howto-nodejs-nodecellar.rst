Node Cellar
===========

A well known example application for Node.js and MongoDB is the `Node cellar
<https://github.com/ccoenraets/nodecellar>`_ application, which keeps a track
of wines in a collection.

You can easily modify this to run on Paasmaker.

We maintain a `fork with our changes <https://github.com/paasmaker/nodecellar>`_ that you
can deploy from directly to try this out. Otherwise, you can follow the documentation
here to see what we changed.

.. note::
	Our example currently only works on local machines with development Paasmaker
	installations. This is because we don't have proper MongoDB support at this
	time. This example relies on the managed MongoDB plugin, which starts up a
	local MongoDB instance on demand for you.

Getting started
---------------

If you want to follow along, start by creating your own fork of the original
repostiory from `https://github.com/ccoenraets/nodecellar <https://github.com/ccoenraets/nodecellar>`_.

Once you've cloned it, there are only a few changes to make.

Firstly, add a ``manifest.yml`` file:

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: nodecellar
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.node.nvm
	      version: v0.8
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - npm update

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.node.nvm
	      version: v0.8
	      parameters:
	        launch_command: node server.js
	    placement:
	      plugin: paasmaker.placement.default

	services:
	  - name: mongodb
	    plugin: paasmaker.service.managedmongodb

Add the Paasmaker interface as a dependency in ``package.json``:

.. code-block:: json

	{
	    "name": "wine-cellar",
	    "description": "Wine Cellar Application",
	    "version": "0.0.1",
	    "private": true,
	    "dependencies": {
	        "express": "3.x",
	        "mongodb": "1.1.8",
	        "socket.io": "0.9.10",
		    "paasmaker": ">=0.9.0"
	    },
	    "engines": {
	        "node": "0.8.4",
	        "npm": "1.1.49"
	    }
	}

Edit the file ``routes/wines.js`` to use the Paasmaker interface
to find the connection credentials for MongoDB. Make the top of the
file read as follows:

.. code-block:: javascript

	var mongo = require('mongodb');
	var paasmaker = require('paasmaker');

	var Server = mongo.Server,
	    Db = mongo.Db,
	    BSON = mongo.BSONPure;

	var pm = new paasmaker();
	var server = new Server(pm.getService('mongodb').hostname, pm.getService('mongodb').port, {auto_reconnect: true});
	db = new Db('winedb', server, {safe: true});

And lastly, edit ``server.js`` to get it to read the TCP port
from the environment:

.. code-block:: javascript

	// ...
	app.configure(function () {
	    app.set('port', pm.getPort() || 3000);
	    app.use(express.logger('dev'));  /* 'default', 'short', 'tiny', 'dev' */
	    app.use(express.bodyParser()),
	    app.use(express.static(path.join(__dirname, 'public')));
	});
	// ...

You can commit these changes, and then deploy to your local Paasmaker
to see it in action.

`This commit on github <https://github.com/paasmaker/nodecellar/commit/de22f6ecb8bb2e4cfe854aa458c604ee4266e434>`_
shows all the changes in one batch.
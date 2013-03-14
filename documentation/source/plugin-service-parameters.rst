Parameters Passthrough Service
==============================

This service just takes whatever values the application provides and places
that into the credentials for the service. It is designed as an example
service, but may find other uses.

In your application manifest, if you place this:

.. code-block:: yaml

	services:
	  - name: variables
	    plugin: paasmaker.service.parameters
	    parameters:
	      one: two

Then your application will have a service called ``variables`` with
the representation of ``{'one': 'two'}``. You can place whatever you
like in the parameters, as long as it can be represented by YAML and JSON.

If you deploy a new version of your application with different parameters,
the credentials are updated to have those parameters.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.parameters.ParametersService
	  name: paasmaker.service.parameters
	  title: Parameters Service

Application Configuration
-------------------------

This plugin just passes the entirety of the parameters into the service
credentials.

Server Configuration
--------------------

This plugin has no server configuration options.
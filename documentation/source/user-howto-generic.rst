Supporting any language
=======================

Paasmaker talks to applications by setting environment variables with the information
that they need. Practically any language can read and work with environment variables.
The only other requirement is the ability to parse JSON, but this is also equally
ubiquitous these days.

PM_PORT
-------

This environment variable is an integer number that is the TCP port that the application
should be listening on.

PM_SERVICES
-----------

This environment variable contains a JSON encoded representation of the services assigned
to the application. The top level object contains a key for every service that is mentioned
in your manifest, and the keys are the user supplied service names. Those keys map to an
object that is the credentials for that service.

How you use these credentials does depend on what the service is. All services should contain
a ``protocol`` key which will indicate what to do with the service.

An example service set encoded in JSON will look like this:

.. code-block:: json

	{
	    "service-name": {
	        "protocol": "mysql",
	        "hostname": "hostname",
	        "database": "database",
	        "username": "username",
	        "password": "password",
	        "port": 3306
	    }
	}

PM_METADATA
-----------

This environment variable contains a selected set of metadata about the application in
question. It can be used to make decisions about what environment to run your application
in (for example, development/staging/production), or what version of the application you
are.

The ``node`` and ``workspace`` key will contain an object that is the tags for the node
that you're on, and the workspace that you're part of. Typically, to determine the environment
for your application, you would check a tag in the ``workspace`` object.

For example, the :doc:`Rails interface <user-howto-ruby-rails>` checks for a ``RAILS_ENV``
key in the workspace tags, and uses that value as the environment if found.

An example encoded block will look like this:

.. code-block:: json

	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 1,
	        "version_id": 4,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

Writing an interface
--------------------

The PHP, Ruby, and Python interfaces all look very similar. Basically, they
have identical structures except the function names match the languages common
conventions, and they look for special keys for specific frameworks.

The interfaces also have a unique feature; when not running on Paasmaker,
they can load the missing values from a YAML or JSON file. The reasoning here
is that you will need to modify your application to run on Paasmaker, but
there are times and situations where you need to run the code outside of Paasmaker
(for development specifically, when you're not using the developer mode of
Paasmaker on your local machine). These configuration files are that balance,
meaning once you've modified your code, you still have the option to run it
without Paasmaker without updating your code again.

Any language interfaces must support loading the missing values from an
external configuration file.
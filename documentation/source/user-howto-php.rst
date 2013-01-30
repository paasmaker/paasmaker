PHP Support
===========

Paasmaker is able to run PHP applications. By default, it will use version 5.3.
The implementation starts up an Apache 2 server per heart node, and all applications
run under that server instance. Each instance is given it's own virtual host for
that application, with a seperate port.

Integrating with common Frameworks and CMSs
-------------------------------------------

The guides below show how to integrate Paasmaker with some common PHP frameworks
and CMS systems, including pitfalls for them.

.. toctree::
   :maxdepth: 2

   user-howto-php-wordpress

Integrating with any PHP project
--------------------------------

If you're using your own PHP framework, or a framework not documented, you should
be able to integrate Paasmaker easily into that system.

If you're using composer in your project, you can install the interface easily with
the following command:

.. code-block:: bash

	$ composer.phar require paasmaker/interface
	$ composer.phar install

If you are not using composer, you will need to fetch the PmInterface.php file and
check it into your project. You can get the latest version from `the BitBucket
repository <https://bitbucket.org/freefoote/paasmaker-interface-php/src>`_.

Once you've included the file, and loaded it in (using ``require()`` if you're not
using composer or an autoloader), you can start it up and query it as follows:

.. code-block:: php

	$interface = \Paasmaker\PmInterface(array('../my-project.json'));
	// Or to allow loading YAML files - you will need the YAML Symfony2 component
	// installed via composer for this to work.
	$interface = \Paasmaker\PmInterface(array('../my-project.yml'), TRUE);

	// This returns true if running on Paasmaker.
	$interface.isOnPaasmaker();

	// Throws \Paasmaker\PmInterfaceException if no such service exists.
	$service = $interface->getService('named-service');

	// $service now contains an array of parameters. Typically this will
	// have the keys 'hostname', 'username', 'password', etc. Use this to
	// connect to the relevant services.

	// Get other application metadata.
	$application = $interface->getApplicationName();
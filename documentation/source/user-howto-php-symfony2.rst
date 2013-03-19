Symfony2 on Paasmaker
=====================

Symfony2 fits very well on Paasmaker, and is a modern PHP web framework. You
can read more about it on `Symfony's website <http://symfony.com>`_.

Getting Started
---------------

For this guide, we're assuming that:

* You have a local installation of Paasmaker for development, that's configured
  with the development mode plugin.
* Your local installation of Paasmaker has the PHP runtime enabled and configured.
* You are using some kind of source control to manage your code. In this example,
  we use Git to manage this.
* You have composer already installed. If not, get it from `the Composer website
  <http://getcomposer.org/>`_. Also, the instructions in this guide assume a system
  wide install of composer; if that's not the case, replace ``composer.phar`` with
  ``php /path/to/composer.phar`` in the instructions.

.. note::
	This guide isn't about how to use Symfony. Its only purpose is to show you
	how to use Symfony 2 with Paasmaker.

	The `Symfony 2 documentation <http://symfony.com/doc/current/index.html>`_ is
	quite extensive and should bring you up to speed.

Versions
--------

This guide is written against the current stable version, 2.2. It differs slightly
from 2.1 or 2.0 in the initialisation. Getting it working on older versions should
not be too difficult.

Creating the initial project
----------------------------

From the `Symfony website <http://symfony.com/download>`_, I used their composer
install instructions. We immediately check in the clean files so we can see what
we changed later.

.. code-block:: bash

	$ composer.phar create-project symfony/framework-standard-edition \
	paasmaker-symfony2 2.2.0
	$ cd paasmaker-symfony2
	$ git init .
	$ git add .
	$ git commit

Now we add the Paasmaker interface to your composer dependencies:

.. code-block:: bash

	$ composer.phar require paasmaker/interface dev-master
	$ git add .
	$ git commit

Next step is to get Symfony to load Paasmaker variables during startup.
In ``app/AppKernel.php``, you will need to add a constructor that loads variables
from Paasmaker. This configuration also reads the environment from the
workspace it's contained in, allowing you to easily switch between dev
and production.

.. code-block:: php

	<?php
	// In file app/AppKernel.php
	// ...
	class AppKernel extends Kernel
	{
	    public function __construct($environment, $debug)
	    {
	        $interface = new \Paasmaker\PmInterface(array(), FALSE);
	        $interface->symfonyUnpack();

	        $paasmakerEnvironment = $interface->getSymfonyEnvironment('prod');
	        $paasmakerDebug = FALSE;
	        if($paasmakerEnvironment == 'dev')
	        {
	        	$paasmakerDebug = TRUE;
	        }

	        parent::__construct($paasmakerEnvironment, $paasmakerDebug);
	    }
	// ...

To switch environments, edit the workspace inside Paasmaker, and create
a tag at the top level called ``SYMFONY_ENV`` with the value matching
the environment that you want. For this example, go ahead and do that now
and set the value to ``dev``.

.. note::
	We've overidden the constructor here, so the values passed in
	from ``web/app.php`` and ``web/app_dev.php`` no longer apply.
	This means you can just use ``app.php`` for development and
	production.

.. note::
	If you don't have a ``SYMFONY_ENV`` tag, it assumes that the
	environment is ``prod``. You can change this with the argument
	to ``getSymfonyEnvironment()``.

Now, add a Paasmaker manifest file. It should look like this:

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: paasmaker-symfony2

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.php
	      version: 5.3
	      parameters:
	        document_root: web

	services:
	  - name: symfonysql
	    plugin: paasmaker.service.mysql

.. note::
	If you're using Ubuntu 12.10 or above, you might have PHP 5.4 installed.
	You can check with ``php -v``. If so, replace "5.3" with "5.4" in the
	manifest file.

Check in your changes:

.. code-block:: bash

	$ git add .
	$ git commit

And exclude the file that Paasmaker is about to create that does
not need to be checked in:

.. code-block:: bash

	$ echo "/paasmaker_env_web.sh" >> .gitignore
	$ git add .
	$ git commit

Now you can create a new application in Paasmaker, using the
development directory SCM, and pass in the directory where you have
the files stored. You can then start that version of the application up.

.. note::
	PHP has the nice side effect of checking if the files have changed
	each request, so you shouldn't need to stop and restart your application.

If you visit your started application (mine is at `http://1.web.paasmaker-symfony2.test.local.paasmaker.net:42530/
<http://1.web.paasmaker-symfony2.test.local.paasmaker.net:42530/>`_). You will see
a Symfony welcome page.

.. note::
	Getting a 404? Make sure you set the ``SYMFONY_ENV`` tag on your workspace.
	The default routes only apply in the ``dev`` environment. If you change
	your workspace after you start the application, you'll need to stop it,
	deregister it, and then start it again.

.. note::
	Getting a 500 error? If you go to the version page and see a list of
	instances, next to each instance is a little icon with lines in it. If
	you expand that, you see Apache's error log for this instance. The PHP
	error should be logged in there, depending on your system's PHP setup.

Working with the database
-------------------------

The example manifest above allocated a MySQL database to our application.
The Paasmaker interface unpacks the service details so you can use them
in your configuration YAML files. So, edit ``app/config/parameters.yml``
as shown here. Note that the name you gave the service in the manifest
file is inserted into the keys:

.. code-block:: yaml

	parameters:
	    database_driver:   pdo_mysql
	    database_host:     %pm.symfonysql.hostname%
	    database_port:     %pm.symfonysql.port%
	    database_name:     %pm.symfonysql.database%
	    database_user:     %pm.symfonysql.username%
	    database_password: %pm.symfonysql.password%

	    mailer_transport:  smtp
	    mailer_host:       127.0.0.1
	    mailer_user:       ~
	    mailer_password:   ~

	    locale:            en
	    secret:            ThisTokenIsNotSoSecretChangeIt

Check in these changes again:

.. code-block:: bash

	$ git add .
	$ git commit

Now create an example model object. These snippets are taken
from the `Doctrine section of the Symfony2 book
<http://symfony.com/doc/current/book/doctrine.html>`_.

.. note::
	You won't be able to use ``php app/console doctrine:database:create`` and
	``php app/console doctrine:database:drop`` as per the book. This is
	because Paasmaker manages the creation of the database for you.

	If you need to empty out the database, Symfony offers the ``doctrine:schema:drop``
	option which should do what you need it to do.

Create the bundle and a ORM object. Note that these are run under
the ``paasmaker_env_web.sh`` script so they are in the correct context.

.. code-block:: bash

	$ ./paasmaker_env_web.sh php app/console generate:bundle --namespace=Acme/StoreBundle
	... accept the defaults when prompted ...
	$ ./paasmaker_env_web.sh php app/console doctrine:generate:entity
	... and enter:
	The Entity shortcut name: AcmeStoreBundle:Product
	New field name (press <return> to stop adding fields): name
	Field type [string]:
	Field length [255]:
	New field name (press <return> to stop adding fields): price
	Field type [string]: float
	New field name (press <return> to stop adding fields): description
	Field type [string]: text
	New field name (press <return> to stop adding fields):

	For everything else, accept the defaults.

Now you can use the standard way to sync up the objects in the database:

.. code-block:: bash

	$ ./paasmaker_env_web.sh php app/console doctrine:schema:update --force
	Updating database schema...
	Database schema updated successfully! "1" queries were executed

If you forget to execute it in the context of the running application, you
will get a somewhat ugly error instead:

.. code-block:: bash

	$ php app/console doctrine:schema:update --force
	PHP Fatal error:  Uncaught exception 'Paasmaker\PmInterfaceException' with message 'Unable to find an override configuration to load.' in /home/daniel/dev/samples/paasmaker-symfony2/vendor/paasmaker/interface/Paasmaker/PmInterface.php:113
	Stack trace:
	#0 /home/daniel/dev/samples/paasmaker-symfony2/vendor/paasmaker/interface/Paasmaker/PmInterface.php(75): Paasmaker\PmInterface->_loadConfigurationFile()
	#1 /home/daniel/dev/samples/paasmaker-symfony2/vendor/paasmaker/interface/Paasmaker/PmInterface.php(49): Paasmaker\PmInterface->_parseMetadata()
	#2 /home/daniel/dev/samples/paasmaker-symfony2/app/AppKernel.php(10): Paasmaker\PmInterface->__construct(Array, false)
	#3 /home/daniel/dev/samples/paasmaker-symfony2/app/console(20): AppKernel->__construct('dev', true)
	#4 {main}
	  thrown in /home/daniel/dev/samples/paasmaker-symfony2/vendor/paasmaker/interface/Paasmaker/PmInterface.php on line 113

The remainder of development with Symfony is as per usual.

File uploads
------------

As stated in other places, in production, Paasmaker deletes files when it is
done with an instance. You'll want to upload files to a remote storage location
rather than the local directory.

Symfony contains a number of bundles that can handle this for you, depending
on your requirements and workflow.

If you use Amazon S3, Paasmaker comes with a plugin that can create Amazon S3
buckets for you. You can then fetch the credentials from the service in the
same way that you fetch other service credentials.

Going into production
---------------------

Typically, you won't be checking in the contents of the ``vendor/`` directory,
as they're external libraries and can be fetched quickly from the internet.
So when you deploy with Paasmaker, it will need to use composer to fetch those dependencies.

The first step is to ensure that your production servers have composer installed.
This is an exercise left up to the reader.

Once that's done, this manifest file will install the dependencies during the
prepare phase of creating a new version. The important lines are hilighted:

.. literalinclude:: support/symfony2-manifest-prepare.yml
	:language: yaml
	:emphasize-lines: 6-14

This will run ``composer.phar install`` when preparing the application. Thanks
to recent updates to composer, this should read from a cache after the first time,
speeding up new application deployments.

Also, the next question is how to handle database updates. In the example manifest,
we run the schema update during the startup phase. The important lines are hilighted:

.. literalinclude:: support/symfony2-manifest-prepare.yml
	:language: yaml
	:emphasize-lines: 24-28

.. warning::
	Using ``doctrine:schema:update`` is not advised according to the Symfony2
	developers. You should heed their advice. Ideally, you would want to set up
	and implement a migrations bundle, but this is outside the scope of this
	document. This example here is just to get you started.

.. warning::
	If you're trying to test this by zipping up your project and uploading it,
	make sure you empty out the ``app/cache`` and ``app/logs`` directories first.
	Otherwise, you will get an error when starting your application.
Getting started with Paasmaker
==============================

This tutorial is designed to get you started and introduced with
the basic concepts of Paasmaker. At the end of it, you will have
the simplest possible web application running on Paasmaker.

For this tutorial we are using Python, purely for simplicity.
Paasmaker ships with support for :doc:`PHP <user-howto-php>` and
:doc:`Ruby <user-howto-ruby>`, so once you've completed this
tutorial, head over to the documents for your faviourite language.

Prerequisites
-------------

We are going to assume that you have installed Paasmaker as
per the :doc:`simple installation guide <installation>`. To make sure
your environment is correct, just check that:

* You have Paasmaker running on your machine;
* You can log into the web control panel for it via
  `http://pacemaker.local.paasmaker.net:42530/ <http://pacemaker.local.paasmaker.net:42530/>`_;
* Your ``paasmaker.yml`` has the DevDirectory plugin enabled.

Your simple web application
---------------------------

Create a directory on your machine that you'll be working in. Then
create ``app.py`` with the following contents:

.. code-block:: bash

	$ mkdir paasmaker-tutorial
	$ gedit app.py

.. literalinclude:: support/tutorial-app-1.py
	:language: python

You can quickly test the Python script locally to make sure it works.
It will start up, listen on port 8000 for HTTP connections, and you
can visit that `in your web browser <http://localhost:8000>`_ and get back
'Hello, World!'. Hit CTRL+C to cancel it.

.. code-block:: bash

	$ python app.py
	Listening for requests at http://localhost:8000
	localhost.localdomain - - [19/Mar/2013 09:18:06] "GET / HTTP/1.1" 200 -
	localhost.localdomain - - [19/Mar/2013 09:18:06] "GET /favicon.ico HTTP/1.1" 200 -
	^CTraceback (most recent call last):
	  File "app.py", line 22, in <module>
	    httpd.serve_forever()
	  File "/usr/lib/python2.7/SocketServer.py", line 225, in serve_forever
	    r, w, e = select.select([self], [], [], poll_interval)
	KeyboardInterrupt

We can't run this on Paasmaker just yet. On startup, it listens on port 8000 only.
This means Paasmaker can't run two instances of your application, or two different
versions of your application. Also, Paasmaker doesn't know what port you selected
and thus can not route requests to it.

To get around this, Paasmaker selects a TCP port for your application instance to
listen on, and supplies that in the ``PM_PORT`` environment variable. To get our
example application to listen to this, we need to tweak it a little bit:

.. literalinclude:: support/tutorial-app-2.py
	:language: python
	:emphasize-lines: 12-14

Run it again to make sure that it works properly. And also try setting the PM_PORT
environment variable, and you'll see that it listens on that port:

.. code-block:: bash

	$ python app.py
	Listening for requests at http://localhost:8000
	CTRL+C
	$ PM_PORT=9001 python app.py
	Listening for requests at http://localhost:9001

Now we have the minimum requirements to run this application on Paasmaker.

Manifest file
-------------

Every Paasmaker application needs a manifest file, to describe to Paasmaker
how to run the application, and to set any Paasmaker related options. It's
a file in YAML format, and is stored as a file because it is meant to be
version controlled.

You should create a manifest file now with these contents. Call it ``manifest.yml``:

.. literalinclude:: support/tutorial-manifest-1.yml
	:language: yaml

.. NOTE::
	YAML can't be indented with tabs. You must use spaces.

You can view the :doc:`full reference for manifest files <user-application-manifest>`
to see all the options you can place in this file, but for now here is the file
with some additional comments:

.. literalinclude:: support/tutorial-manifest-1-commented.yml
	:language: yaml

Now that we have a manifest file, we're going to add the
application to our local Paasmaker, using the special
development directory SCM plugin. This bypasses a few of
the normal proceedures for Paasmaker, allowing you to develop
using Paasmaker.

Find out what directory you have been creating your files in:

.. code-block:: bash

	$ pwd
	/home/daniel/dev/samples/paasmaker-tutorial

Copy that out, and go to create a new application inside a workspace.
From the available SCMs, choose "Development Local Directory SCM",
and in the "Local Directory" box paste in the directory you found
above. Then click "Create".

If you had an error in your manifest file, the job will fail, and it
should give you a moderately helpful error as to why it failed.

.. NOTE::
	The development local directory SCM skips the prepare and startup
	tasks from the manifest file. These concepts haven't been introduced
	yet, but will be shortly.

Now you will have a prepared version of the application in the control panel.
If you view the versions of it, you should see "Version 1". Near that will
be a button marked "Start". Click it, and wait for the jobs to complete.

Once it has started, the page for that version will contain the URL that
it assigned the application. This URL is used to access that specific running
version and type of that application. In this example, it should be
`http://1.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://1.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_. If you
visit that link, you will get the same "Hello World!" message that your local
script generated when you ran it manually.

You will also notice that a new file, ``paasmaker_env_web.sh`` has appeared
in your local directory. It has a special use talked about later. You should
exclude checking in this file from your source control system.

Making changes
--------------

If you change the ``app.py`` file now, you won't see any of the changes
when you reload the page. This is because once ``app.py`` starts, it doesn't
see any code changes to itself.

Many frameworks already have ways to handle this, and you can leverage those
to handle reloading in development. The :doc:`user manual <user>` covers how to handle
this with popular frameworks.

For our simple application, we are not going to implement a reload feature, so you
will need to stop the version (using the button in the control panel) and start it
again to see changes.

Reporting more information
--------------------------

We are going to make a few changes to our application to output more information
about it's environment, which we'll then use in the next few tutorial steps to
show a bit more about how Paasmaker works internally.

Update your ``app.py`` as follows:

.. literalinclude:: support/tutorial-app-3.py
	:language: python
	:emphasize-lines: 12-14

Run it locally again just to make sure that you don't have any syntax errors.

.. code-block:: bash

	$ python app.py

If you visit your locally running version (not via Paasmaker - so through
`http://localhost:8000 <http://localhost:8000>`_) you should get this output:

.. code-block:: none

	My working directory: /home/daniel/dev/samples/paasmaker-tutorial
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* app.py
	Contents of PM_SERVICES:
	- No contents, variable not set.
	Contents of PM_METADATA:
	- No contents, variable not set.

Now, in Paasmaker, stop and restart your version. Then visit the Paasmaker
controlled version via `http://1.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://1.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_. You should
get output similar to this, although your ID numbers may be different:

.. code-block:: none

	My working directory: /home/daniel/dev/samples/paasmaker-tutorial
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* app.py
	Contents of PM_SERVICES:
	{}
	Contents of PM_METADATA:
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

Notice that the ``PM_SERVICES`` and ``PM_METADATA`` environment variables are
set. They contain a JSON encoded string containing information about the application.

Services
--------

The next concept we are going to introduce is services. Paasmaker uses the
term services to mean resources that an application needs to run, such
as a SQL database. Paasmaker is designed to create and managed these services
for you, and supply the credentials to your application. This means that your
application can be written and not have hard coded values. It also means
that in development, Paasmaker can do the heavy lifting of creating the
database for you. So let's update our manifest file to add a MySQL database:

.. literalinclude:: support/tutorial-manifest-2.yml
	:language: yaml
	:emphasize-lines: 16-18

Manifest files are only re-read when you deploy a new version. So, via the
web console, find the 'Create New Version' button. It will prefill the form
with the correct source location and the values you supplied last time, so you
can just click 'Create'.

Be patient whilst it creates the new version, which includes setting up
a new MySQL database for you.

Now you will have two versions. You can stop the old version of the tutorial
application, and start your new version up. Then visit it via your web
browser at `http://2.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://2.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_. Your
output will now look something like this:

.. code-block:: none

	My working directory: /home/daniel/dev/samples/paasmaker-tutorial
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* app.py
	Contents of PM_SERVICES:
	{
	    "mysqldatabase": {
	        "database": "mysqldat98e98a46",
	        "hostname": "127.0.0.1",
	        "password": "d7fc97b7-3791-4c49-bd28-897c51d14fe8",
	        "port": 42801,
	        "protocol": "mysql",
	        "provider": "paasmaker.service.mysql",
	        "username": "mysqldat98e98a46"
	    }
	}
	Contents of PM_METADATA:
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 3,
	        "version_id": 6,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

You'll notice that there is now some contents inside PM_SERVICES. These details
point to an actual MySQL database that you can connect to. How you connect to
this database is up to the framework that you use for your application; the
:doc:`user manual <user>` shows how to do this for common frameworks. However,
you should be able to implement it for any framework or application.

.. note::
	The MySQL database here is on a non-standard port. This is because in
	the development installation, Paasmaker starts up a MySQL database for you
	on demand and grants access to it. In production, your system administrator
	would have pointed that database to a more appropriate actual database
	server.

Accessing the environment in command line scripts
-------------------------------------------------

So your application, when running on Paasmaker, is supplied with the correct
environment variables so that it can access services. But during development,
you will want to run local scripts in that context - for example, database
schema import scripts.

Paasmaker creates a ``paasmaker_env_web.sh`` script for this purpose. To
demonstrate this, we're going to create a second Python script, called
``commandline.py``, with the following contents. This is just an adaptation
of app.py that doesn't have any HTTP handling:

.. literalinclude:: support/tutorial-commandline-1.py
	:language: python

Now, if you run this raw on the command line, it won't have any of the
Paasmaker variables. But if you run it using the ``paasmaker_env_web.sh``
script, it will have the correct environment:

.. code-block:: bash

	$ python commandline.py
	My working directory: /home/daniel/dev/samples/paasmaker-tutorial
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* commandline.py
	* app.py
	Contents of PM_SERVICES:
	- No contents, variable not set.
	Contents of PM_METADATA:
	- No contents, variable not set.

.. code-block:: bash

	$ ./paasmaker_env_web.sh python commandline.py
	My working directory: /home/daniel/dev/samples/paasmaker-tutorial
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* commandline.py
	* app.py
	Contents of PM_SERVICES:
	{
	    "mysqldatabase": {
	        "database": "mysqldat98e98a46",
	        "hostname": "127.0.0.1",
	        "password": "d7fc97b7-3791-4c49-bd28-897c51d14fe8",
	        "port": 42801,
	        "protocol": "mysql",
	        "provider": "paasmaker.service.mysql",
	        "username": "mysqldat98e98a46"
	    }
	}
	Contents of PM_METADATA:
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 3,
	        "version_id": 6,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

If you modify your frameworks's startup code so that it reads this data
early enough, most things will work without further modification.

How it differs in production
----------------------------

Up until this stage, we've been running in a special development mode.
In production, you won't be doing this. So now we'll deploy the same
application using a similar method to what you will use in production,
and see what the output is instead.

Firstly, zip up all the files so you can supply them to Paasmaker:

.. code-block:: bash

	$ zip paasmaker-tutorial.zip app.py manifest.yml

Now from the web console, you can create a new version of your tutorial
application. Instead of using the existing details in the "Development Local
Directory SCM" section, click "Show" under "Zip file SCM". Using the button,
upload the zip file you created just then and click Create.

Once this version is ready, start it, and then visit the URL for that version.
It should be version 3 at this stage. The URL should be
`http://3.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://3.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.

The abridged output is shown below. The important part here is the first line;
you will notice that it's not the directory you developed in before. This
is because in production, Paasmaker chooses a location for your instance to
run in.

.. code-block:: none

	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/0678e91a-e0ec-4dc5-a844-6632fabe735e
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* app.py

If you stop your version, and then use the "De-register" button, and then
start it again, and visit the URL, you will get a different directory again.
As soon as you hit de-register, the instance directory is permanently deleted.
Your application shouldn't be writing any files into that directory if it does
not want to lose them. This could be considered a limitation of Platforms as a
Service, however, it is the balance that allows them to scale applications and
work around failures easily. If you want to keep files permanently, store them
in an external location such as Amazon S3.

In this case, if I deregister and start again, I get:

.. code-block:: none

	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/b7bf8631-eab5-4849-b0b1-43e3e18761a4
	Files in my working directory:
	* paasmaker_env_web.sh
	* manifest.yml
	* app.py

Multiple instances
------------------

Update your manifest file slightly to increase the number of instances
of the web instance type:

.. literalinclude:: support/tutorial-manifest-3.yml
	:language: yaml
	:emphasize-lines: 9

Now zip up the files again, and create a new version in the console using that
zip file:

.. code-block:: bash

	$ zip paasmaker-tutorial.zip app.py manifest.yml

Start up that version of the application, and visit the URL for it. It should be
`http://4.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://4.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.
Reload it a few times, and note that the working directory changes randomly between
two different directories. So your output will change between something like these:

.. code-block:: none

	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/d700b0d6-c895-4c2b-9899-03d97f93809f
	.. or ..
	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/15381d56-3e37-4ac0-98ee-ceebbcdc2a37

What is happening here is that the router is choosing an instance, at random, to direct
your request to. These instances don't need to be on the same physical server, and for
redundancy should not be.

.. note::
	At the moment, the router just randomly routes requests between available instances.
	In the future, we hope to have stickyness settings, so requests from the same client
	go back to the same instance each time.

Prepare tasks
-------------

Typically, Paasmaker will be used with a source control system. In many modern projects,
each project contains a file that describes what other libraries it uses. The libraries
might be downloaded with a tool and stored in the same directory as the application.
To keep the size of the repository down, these are often not checked into source control.

So, Paasmaker needs a way to be able to fetch any other files that it needs during
the prepare phase. For this, you can specify prepare tasks in your manifest file.
They are plugin based, but a common plugin just runs shell commands.

To demonstrate this, update your manifest file as shown:

.. literalinclude:: support/tutorial-manifest-4.yml
	:language: yaml
	:emphasize-lines: 6-14

Now zip up and create a new version of your application. Start it and view the output at
`http://5.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://5.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.

.. code-block:: bash

	$ zip paasmaker-tutorial.zip app.py manifest.yml

.. code-block:: none

	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/758dd87c-aa59-481f-b068-6b6f9745802f
	Files in my working directory:
	* paasmaker_env_web.sh
	* prepare.txt
	* manifest.yml
	* app.py

Note that ``prepare.txt`` appears in the list of files in the working directory.
We're going to read it's contents. Your path will be different below, but you
can determine it from the working directory in your output:

.. code-block:: bash

	$ cat /home/daniel/dev/paasmaker/scratch/instances/instance/758dd87c-aa59-481f-b068-6b6f9745802f/prepare.txt
	/home/daniel/dev/paasmaker/scratch/scm/ZipSCM/39294ed0-ce95-4a63-a96e-d290350efeac

Note that the directory doesn't match the instance directory. This is because
during the prepare phase, Paasmaker is using a temporary directory to prepare
your application. Your application is then packed up, and passed along to the
server that will actually execute it, which then unpacks it's own copy of it.
For a full description of the prepare phase and what it does is, see the
:ref:`documentation on an application lifecycle <user-application-lifecycle>`.

Startup tasks
-------------

Just before your application starts, you may want to perform some other things
to get ready - such as compiling assets, that you need to do on the actual
server that will be running your application. These are also plugin based.

Update your manifest file as follows:

.. literalinclude:: support/tutorial-manifest-5.yml
	:language: yaml
	:emphasize-lines: 24-28

Now zip up and create a new version of your application. Start it and view the output at
`http://6.web.paasmaker-tutorial.test.local.paasmaker.net:42530/
<http://6.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.

.. code-block:: bash

	$ zip paasmaker-tutorial.zip app.py manifest.yml

.. code-block:: none

	My working directory: /home/daniel/dev/paasmaker/scratch/instances/instance/ce5cd62c-6ea6-4294-9944-971b9dad8e21
	Files in my working directory:
	* startup.txt
	* prepare.txt
	* manifest.yml
	* app.py

Note that now there is a ``startup.txt`` file. If you view the contents of the file
(and you will need to adjust your path to get this to work):

.. code-block:: bash

	$ cat /home/daniel/dev/paasmaker/scratch/instances/instance/ce5cd62c-6ea6-4294-9944-971b9dad8e21/startup.txt
	/home/daniel/dev/paasmaker/scratch/instances/instance/ce5cd62c-6ea6-4294-9944-971b9dad8e21

You will notice that the directory matches your instance directory. So the current
working directory for startup tasks is that instances directory.

Hostnames
---------

The last concept we want to introduce to Paasmaker is hostnames. Up until this
point, you've been using the hostnames that Paasmaker has been allocating for
your application. But in production, you'll want to use something a bit nicer.

As a convenience for users, we've added a wildcard DNS record for ``*.local.paasmaker.net``,
which is how this tutorial works for you on your local machine. Using this
wildcard, we can add a domain name to your application. Add the following to your
manifest file:

.. literalinclude:: support/tutorial-manifest-6.yml
	:language: yaml
	:emphasize-lines: 29-30

Now, zip up your application, and create two new versions with the exact same
zip file. These should be versions 7 and 8, with the following version specific
domain names:

* `http://7.web.paasmaker-tutorial.test.local.paasmaker.net:42530/ <http://7.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.
* `http://8.web.paasmaker-tutorial.test.local.paasmaker.net:42530/ <http://8.web.paasmaker-tutorial.test.local.paasmaker.net:42530/>`_.

.. code-block:: bash

	$ zip paasmaker-tutorial.zip app.py manifest.yml

And start both versions at the same time, and check you can see them. Each
one will report a different version that it is:

.. code-block:: none

	...
	Contents of PM_METADATA:
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 7,
	        "version_id": 8,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}
	...
	Contents of PM_METADATA:
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 8,
	        "version_id": 9,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

However, if you try the domain name that you set up in the manifest file, you'll get
an error. Try visiting `http://tutorial.local.paasmaker.net:42530/ <http://tutorial.local.paasmaker.net:42530/>`_.
This is because there is no current version of the application, and Paasmaker doesn't route
traffic because it doesn't know what version to use.

On the version list page, next to the running versions, you'll notice a button marked
"Make Current". Find version 7, and click that button. This will take you to a job
tree page whilst it rearranges the routing table. The :ref:`documentation on an
application lifecycle <user-application-lifecycle-routing-switchover>` describes how
the routing is updated to prevent dropping public traffic.

Now if you visit `http://tutorial.local.paasmaker.net:42530/ <http://tutorial.local.paasmaker.net:42530/>`_,
you'll get version 7:

.. code-block:: none

	...
	Contents of PM_METADATA:
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 7,
	        "version_id": 8,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

If you go back to the versions list page, and click the "Make Current" button
next to version 8, and then try visiting `http://tutorial.local.paasmaker.net:42530/ <http://tutorial.local.paasmaker.net:42530/>`_,
again, you'll get version 8 instead:

.. code-block:: none

	...
	{
	    "application": {
	        "application_id": 4,
	        "name": "paasmaker-tutorial",
	        "version": 5,
	        "version_id": 8,
	        "workspace": "Test",
	        "workspace_stub": "test"
	    },
	    "node": {},
	    "workspace": {}
	}

This applies for as many hostnames as you want to list in your manifest file,
and they are per version too.

Next steps
----------

Paasmaker has quite a number of other features that are not mentioned in this tutorial.
Where you go next depends on what you want to accomplish with Paasmaker.

* If you want to see how to work with particular languages, head on over to the
  :ref:`user manual <user-languages-entry>` to get started with those.
* If you want to learn more in depth about how Paasmaker works, read the full
  :doc:`user concepts <user-concepts>` documentation.
* If you want to see everything you can put into a manifest file, see the
  :doc:`full description of application manifests <user-application-manifest>`.
* If you want to see what production deployments of Paasmaker look like, check
  the :doc:`administrator's manual <administrator>`.
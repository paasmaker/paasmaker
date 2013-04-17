Using the command line tool
===========================

Paasmaker provides a command line tool to interact with Paasmaker remotely.
Internally, the command line tool uses the API to communicate with Paasmaker.

.. WARNING::
	Currently, you need to have a fully checked out and installed version of
	Paasmaker locally to use the command line tool. We hope to break this out
	soon so you can install just the command line tool seperately.

Commands
--------

Inside the Paasmaker directory is a file called ``pm-command.py``. This is the
command line tool.

If you run it with ``./pm-command.py --help`` or ``./pm-command.py help`` it will
show the list of available sub commands.

Each sub command takes different arguments, which you can see with ``./pm-command.py subcommand --help``.

Authentication and Targetting
-----------------------------

The following options are available to point the command line tool at the
correct location:

``-r REMOTE, --remote REMOTE``: Set the hostname to the REMOTE argument. By default this is localhost.

``-p PORT, --port PORT``: Set the port to the argument. By default this is 42500.

``--ssl``: Enable SSL for the connection.

``-k KEY, --key KEY``: Use the supplied key for authentication. Key can be either your
user API key, or the super key configured for the cluster.

A quirk in the argument parsing means you should have the connection information at the
end of the command line.

As an example, you might connect to a production instance like this:

.. code-block:: bash

	$ ./pm-command.py subcommand arg1 arg2 \
	-r pacemaker.production.paasmaker.net -p 443 --ssl -k <apikey>

Output formats
--------------

By default, the command line tool reports progress via the Python logging
libraries statements, which are written to stderr. Results from the server
are written to stdout. The default output format is "human" which means the
output is parsed into a human readable format.

If you prefer to get the raw responses from the server, you can use the
``--format`` option, by passing either ``json`` or ``yaml`` to select those
outputs.

Following Jobs
--------------

Some commands launch a job on the remote server, and the API call just returns
the job ID. For commands that do this, you can append the option ``--follow``
to follow the status of that job. The ``pm-command.py`` program prints status
information for each job as it becomes available. Once the job reaches a
finished state, ``pm-command.py`` will exit. If the job was successful it
returns a zero (0) exit code, otherwise it will return a one (1) exit code.

If you use the ``--follow`` option with the json output format, the command
will print one json document per status that it gets, which means that you
might need special handling to parse those responses. Alternately, you could
use the yaml format, which prints out document delimiters.

Working with files
------------------

If you use the zip or tarball SCM, you will need to upload a file. In the web
console, these are integrated into a single step. For the command line tool,
these are two steps. Use the ``file-upload`` command first to upload the file
to the remote server. When the file is uploaded, you will get an identifier back,
which you then use with the SCM.

The same technique applies when importing services, as you need to upload a file
containing the contents first.

An example is shown below. Take a note of the identifier returned from the server.

.. code-block:: bash

	$ ./pm-command.py file-upload tts.zip -r ... -p ... -k ...
	2013-04-17 09:01:34,947 INFO Uploading from local file ../tts.zip
	2013-04-17 09:01:35,163 INFO 1048576 bytes of 3398214 uploaded (30.86%).
	2013-04-17 09:01:35,239 INFO 2097152 bytes of 3398214 uploaded (61.71%).
	2013-04-17 09:01:35,319 INFO 3145728 bytes of 3398214 uploaded (92.57%).
	2013-04-17 09:01:35,399 INFO 3398214 bytes of 3398214 uploaded (100.00%).
	2013-04-17 09:01:35,418 INFO Finished uploading file.
	Uploaded file, identifier: 70f14d73a7240c5893dbeaba5c47b093
	$ ./pm-command.py application-new 1 paasmaker.scm.zip --uploadedfile 70f14d73a7240c5893dbeaba5c47b093

.. NOTE::
	You must authenticate with a user API key to upload files. You can not
	upload files by using a super token.

Working with SCMs
-----------------

Currently, to use SCMs that take parameters, you must format these parameters
ahead of time as a JSON string, and pass those in. For example, to use the git
SCM:

.. code-block:: bash

	$ ./pm-command.py application-new 1 paasmaker.scm.git \
	--parameters '{"location":"git@...","revision":"HEAD","branch":"master"}'

Service tunneling
-----------------

To tunnel to a service, you can use the ``service-tunnel`` command. This creates
a listening TCP socket on your machine that you can then connect to, that will
connect you back to the original service.

.. NOTE::
	Currently, due to limitations with the way this is implemented via the remote
	pacemaker, all data across the wire is Base64 encoded. This means it is about
	30% larger than the real data. This feature is still extremely capable for
	running commands against a remote database for troubleshooting purposes, but it is
	not advised to use this feature to backup or import databases. The service import
	and export features are designed to cover off those use cases.

To start the tunnel, use the following command. The credentials for the service
are printed out so you can supply those when connecting.

.. code-block:: bash

	$ ./pm-command.py service-tunnel 7
	2013-04-17 09:10:43,126 INFO Access credentials:
	---
	database: ***************
	hostname: 127.0.0.1
	password: ***************
	port: 42801
	protocol: mysql
	username: ***************
	...

	2013-04-17 09:10:43,131 INFO ** Going to listen on localhost:10010
	2013-04-17 09:10:43,131 INFO ** Press CTRL+C to exit.

You can control the port that it listens on with the ``--localport`` argument,
and also allow binding to a specific interface with the ``--localaddress`` argument.
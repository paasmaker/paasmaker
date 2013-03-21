Redmine on Paasmaker
====================

`Redmine <http://www.redmine.org/>`_, a well known open source issue tracker,
written in Ruby on Rails, can easily be run on Paasmaker.

Getting Started
---------------

For this guide, we're assuming that:

* You have a local installation of Paasmaker for development, that's configured
  with the development mode plugin.
* Your local installation of Paasmaker has the Ruby runtime enabled and configured.
  We're also assuming that you've installed a version of 1.9.3 (any patch level).
* You have rbenv installed for your user and set up.
* You are using some kind of source control to manage your code. In this example,
  we use Git to manage this.

Install Redmine
---------------

Before installing Redmine, if you want to use the image resizing features, you need to install
a few development libraries. On Ubuntu, you can get those libraries with the following command:

.. code-block:: bash

	$ sudo apt-get install imagemagick libmagickwand-dev

.. note::
	Paasmaker doesn't currently have a mechanism to ensure these are installed on
	production servers. You'll need to ensure you've done this ahead of time in production.
	We hope to add a secure way to be able to do this via an application manifest (or other
	method) in the future.

Redmine is available as a tar.gz download, or you can fetch from subversion. In this case,
we're going to export a stable copy from Subversion into our local repository. The reason
that we're taking a copy is to track our updates to Redmine, and also you need a way to get
your version to Paasmaker.

Go into the directory, and export the latest revision. At time of writing, this is
2.3.0, and we ended up with r11670. We immediately check it in to have a pristine version
in our source control system.

.. code-block:: bash

	$ mkdir paasmaker-redmine
	$ cd paasmaker-redmine
	$ git init .
	$ svn export --force http://svn.redmine.org/redmine/branches/2.3-stable/ .
	$ git add .
	$ git commit

Now that we have the files, add a new file, called ``Gemfile.local`` with your local gems.
In it, place the following gems. You will also need to remove ``Gemfile.local`` from ``.gitignore``.

.. code-block:: ruby

	# Create Gemfile.local :
	gem 'thin'
	gem 'paasmaker-interface'

.. code-block:: bash

	$ gedit .gitignore
	... remove Gemfile.local ...

Then install your bundle:

.. code-block:: bash

	$ bundle install

Now, set up a manifest file in the root of the project. Call it ``manifest.yml`` with
the following contents. You should adjust this for your environment.

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: paasmaker-redmine
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.ruby.rbenv
	      version: 1.9.3
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - gem install paasmaker-interface
	            - bundle install --without development test

	instances:
	  - name: web
	    quantity: 1
	    runtime:
	      plugin: paasmaker.runtime.ruby.rbenv
	      parameters:
	        launch_command: "thin start -p %(port)d"
	      version: 1.9.3
	    startup:
	      - plugin: paasmaker.startup.shell
	        parameters:
	          commands:
	            - gem install paasmaker-interface
	            - bundle install --without development test
	            - rake db:migrate
	            - REDMINE_LANG=en rake redmine:load_default_data

	services:
	  - name: redminesql
	    plugin: paasmaker.service.mysql

Now, you can edit ``config/environment.rb`` to make the following changes:

.. literalinclude:: support/redmine-environment.rb
	:language: ruby
	:emphasize-lines: 15-21

Create the file ``paasmaker-placeholder.yml`` in the root with the following contents.
This is a dummy file for the Paasmaker interface to load later on, when you run
``bundle install`` again later.

.. code-block:: yaml

	# Create file paasmaker-placeholder.yml :
	services:
	  redminesql:
	    database: "dummydb"
	    host: "localhost"
	    username: "user"
	    password: "password"
	    port: 3306

	application:
	  name: paasmaker-redmine
	  version: 1
	  workspace: Test
	  workspace_stub: test

Starting from version 2.3, Redmine ships with a Gemfile that reads ``config/database.yml``
to figure out what database gems to install. We are about to modify database.yml to read
values from Paasmaker, which will cause the interface to stop working. If the interface
is not run on Paasmaker, it needs to have an override file to load the missing values from.
The file ``paasmaker-placeholder.yml`` fills in those missing values just enough so that
the Gemfile logic can load the correct database gems.

.. note::
	On versions prior to 2.3, you can skip including ``paasmaker-placeholder.yml``, and referencing
	if in ``config/environment.rb``.

Make a copy of the ``config/database.yml.example`` as ``config/database.yml``. You will
need to remove ``config/database.yml`` from the ``.gitignore`` file, because you will need
to check in the configuration file. This is safe, because with Paasmaker, you're not
checking in actual database credentials, and only placeholders that get replaced at runtime
with the correct values supplied by Paasmaker.

.. code-block:: bash

	$ cp config/database.yml.example config/database.yml
	$ gedit .gitignore
	... remove config/database.yml from .gitignore ...

Once you've copied the ``config/database.yml`` file, adjust it to read as so. Note that in
the call to ``get_service()``, the name matches up with the service name in the
``manifest.yml`` file.

.. code-block:: yaml

	# In file config/database.yml
	<% require 'paasmaker' %>
	<% interface = Paasmaker::Interface.new(['paasmaker-placeholder.yml']) %>
	<% database = interface.get_service('redminesql') %>

	production:
	  adapter: mysql2
	  database: "<%= database['database'] %>"
	  host: "<%= database['hostname'] %>"
	  username: "<%= database['username'] %>"
	  password: "<%= database['password'] %>"
	  port: <%= database['port'] %>

	development:
	  adapter: mysql2
	  database: "<%= database['database'] %>"
	  host: "<%= database['hostname'] %>"
	  username: "<%= database['username'] %>"
	  password: "<%= database['password'] %>"
	  port: <%= database['port'] %>

	# Warning: The database defined as "test" will be erased and
	# re-generated from your development database when you run "rake".
	# Do not set this db to the same as development or production.
	test:
	  adapter: mysql
	  database: redmine_test
	  host: localhost
	  username: root
	  password: ""
	  encoding: utf8

	test_pgsql:
	  adapter: postgresql
	  database: redmine_test
	  host: localhost
	  username: postgres
	  password: "postgres"

	test_sqlite3:
	  adapter: sqlite3
	  database: db/test.sqlite3

Run ``bundle install`` again to pick up the database gems.

.. code-block:: bash

	$ bundle install

You will need to generate a secret token used for logins. There is a command to generate it,
and then you'll need to remove ``/config/initializers/secret_token.rb`` from the .gitignore
so you can check it in:

.. code-block:: bash

	$ rake generate_secret_token
	$ gedit .gitignore
	... remove the line /config/initializers/secret_token.rb ...

.. note::
	Some people will consider that checking in the secret token reduces security. However,
	the expected use of this guide is for people to deploy their own installations of
	Redmine, not to develop or share their installation with other people. If you are not
	sharing your code with another person (or the world generally) then it should be safe
	to check in the token.

Check in all your file updates to this point:

.. code-block:: bash

	$ git add .
	$ git commit

At this stage, you can add the application to your development Paasmaker to test it, but
it won't yet work - and in fact will return a 500 server error. This is because the startup
commands are not run, so the database that it has been assigned is blank. However, in your
development directory, a new file would have appeared - ``paasmaker_env_web.sh`` - which can
be used to access the database as if it was running inside the PaaS. So, run the startup
commands now to bootstrap the database:

.. code-block:: bash

	$ ./paasmaker_env_web.sh rake db:migrate
	$ REDMINE_LANG=en ./paasmaker_env_web.sh rake redmine:load_default_data
	$ echo "/paasmaker_env_web.sh" >> .gitignore

Also, at the moment it will be running in ``production`` mode. This is not what you want for
development. To fix this, edit the workspace that you added the application to, and add
a key called ``RAILS_ENV``, and set it's value to ``development``. Stop, de-register, and
then restart your application. Your application then should start in development mode,
which means autoreloading will work correctly.

.. note::
	Just stopping your instance and starting it again is not enough. You must deregister
	it first, as Paasmaker only updates the instance metadata on instance registration.

Now, you can access your Redmine installation using the default username and password,
``admin`` and ``admin``. It may take a few seconds to load the front page the first time
as the caches are populated.

Storing attachments on Amazon S3
--------------------------------

By default, Redmine will store uploaded files onto the filesystem alongside the code. For
many installations this works well; however, on Paasmaker, all the uploads will vanish when
the instance is deregistered. This poses a problem for long term file storage with Redmine.

However, there is a plugin for Redmine that allows uploading files to Amazon S3. Combine
this with Paasmaker's S3 Bucket service, and we can have it upload files to S3 automatically.

For this example, we're assuming that:

* You have an Amazon S3 account.
* Your development PaaS is configured with the Amazon S3 Bucket service plugin.
* You already have a working Redmine installation created with the method above.

We are using the `redmine_s3 <https://github.com/ka8725/redmine_s3>`_ plugin to handle the
Redmine side of it.

First, update your ``manifest.yml`` file, so the services section looks like as follows. You should
choose an appropriate region for your new bucket.

.. code-block:: yaml

	services:
	  - name: redminesql
	    provider: paasmaker.service.postgres
	  - name: pmredmine
	    provider: paasmaker.service.s3bucket
	    parameters:
	      region: ap-southeast-2

You'll then need to deploy a new version of your development directory with Paasmaker, to
get it to create the new service.

Then, following the redmine_s3 plugin's install guide:

.. code-block:: bash

	$ git clone git://github.com/ka8725/redmine_s3.git plugins/redmine_s3
	$ rm -rf plugins/redmine_s3/.git
	$ cp plugins/redmine_s3/config/s3.yml.example config/s3.yml
	$ ./paasmaker_env_web.sh bundle install

Now edit ``config/s3.yml`` to hook up the bucket it created for you:

.. code-block:: yaml

	<% interface = $PAASMAKER_INTERFACE %>
	<% s3 = interface.get_service('pmredmine') %>

	production:
	  access_key_id: "<%= s3['access_key'] %>"
	  secret_access_key: "<%= s3['secret_key'] %>"
	  bucket: "<%= s3['bucket'] %>"
	  endpoint: "<%= s3['endpoint'] %>"

	development:
	  access_key_id: "<%= s3['access_key'] %>"
	  secret_access_key: "<%= s3['secret_key'] %>"
	  bucket: "<%= s3['bucket'] %>"
	  endpoint: "<%= s3['endpoint'] %>"

Restart the application, and then try to upload some files. You should see
a brand new bucket in your Amazon S3 account, and when you attach files, they
should appear in the bucket automatically. Note that this plugin will make Redmine
slower to upload files, as it has to go to S3 directly, but the result is that
your files are persistent.

Check in your changes, and deploy as appropriate.

Moving to production
--------------------

When you move to production and create the application, it will get it's own
live database and configuration details. You can then configure this as you
need for your environment.
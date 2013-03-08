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
* You have rbenv installed for your user.
* You are using some kind of source control to manage your code. In this example,
  we use Git to manage this.

Create the git repository
-------------------------

Use your normal tools to create a git repository, and hook it up to the remote repository.

For example, with BitBucket, you would do the following:

.. code-block:: bash

	$ mkdir paasmaker-redmine
	$ cd paasmaker-redmine
	$ git init .
	$ git remote add origin ssh://git@bitbucket.org/freefoote/paasmaker-redmine.git
	... make your changes ...
	$ git commit
	$ git push -u origin master

Install Redmine
---------------

Before installing Redmine, if you want to use the image resizing features, you need to install
a few development libraries. On Ubuntu, you can get those libraries with the following command:

.. code-block:: bash

	$ sudo apt-get install imagemagick libmagickwand-dev

Redmine is available as a tar.gz download, or you can fetch from subversion. In this case,
we're going to export a stable copy from Subversion into our local repository. The reason
that we're taking a copy is to track our updates to Redmine.

Go into the directory, and export the latest revision. At time of writing, this is
2.2.2, and we ended up with r11258. We immediately check it in to have a pristine version
in our source control system.

.. code-block:: bash

	$ cd paasmaker-redmine
	$ svn export --force http://svn.redmine.org/redmine/branches/2.2-stable/ .
	$ git add .
	$ git commit

Now that we have the files, add a new file, called ``Gemfile.local`` with your local gems.
In it, place the following gems. You will also need to remove ``Gemfile.local`` from ``.gitignore``.

.. code-block:: ruby

	gem 'thin'
	gem 'paasmaker-interface'

Then update your bundle:

.. code-block:: bash

	$ bundle install

Now, set up a manifest file in the root of the project. Call it ``manifest.yml`` with
the following contents. You should adjust this for your environment. This sets up
Redmine with a Postgres database - if you want a MySQL one instead, use the appropriate
service to do this.

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
	            - bundle install --without development test
	            - rake db:migrate
	            - REDMINE_LANG=en rake redmine:load_default_data
	    placement:
	      plugin: paasmaker.placement.default

	services:
	  - name: redminesql
	    plugin: paasmaker.service.postgres

Now, you can edit ``config/environment.rb`` to make the following changes. The new block
is the one in the middle.

.. code-block:: ruby

	# Load the rails application
	require File.expand_path('../application', __FILE__)

	# Make sure there's no plugin in vendor/plugin before starting
	vendor_plugins_dir = File.join(Rails.root, "vendor", "plugins")
	if Dir.glob(File.join(vendor_plugins_dir, "*")).any?
	  $stderr.puts "Plugins in vendor/plugins (#{vendor_plugins_dir}) are no longer allowed. " +
	    "Please, put your Redmine plugins in the `plugins` directory at the root of your " +
	    "Redmine directory (#{File.join(Rails.root, "plugins")})"
	  exit 1
	end

	# For Paasmaker, determine the rails environment.
	require 'paasmaker'
	interface = Paasmaker::Interface.new([])
	ENV['RAILS_ENV'] = interface.get_rails_env('production')

	# Store the interface into a global variable for later use.
	$PAASMAKER_INTERFACE = interface

	# Initialize the rails application
	RedmineApp::Application.initialize!

Make a copy of the ``config/database.yml.example`` as ``config/database.yml``. You will
need to remove ``config/database.yml`` from the ``.gitignore`` file, because you will need
to check in the configuration file.

Once you've copied the ``config/database.yml`` file, adjust it to read as so. Note that in
the call to ``get_service()``, the name matches up with the service name in the
``manifest.yml`` file.

.. code-block:: yaml

	<% interface = $PAASMAKER_INTERFACE %>
	<% database = interface.get_service('postgres') %>

	production:
	  adapter: postgresql
	  database: "<%= database['database'] %>"
	  host: "<%= database['hostname'] %>"
	  username: "<%= database['username'] %>"
	  password: "<%= database['password'] %>"
	  port: <%= database['port'] %>

	development:
	  adapter: postgresql
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

You will need to generate a secret token used for logins. This command will generate it:

.. code-block:: bash

	$ rake generate_secret_token

However, you will need to remove ``/config/initializers/secret_token.rb`` from ``.gitignore``
to be able to check it in. If you don't check it in and deploy it, the nodes will end up
with different tokens, which will lead to some interesting behaviours in future.

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

Also, at the moment it will be running in 'production' mode. This is not what you want for
development. To fix this, edit the workspace that you added the application to, and add
a key called 'RAILS_ENV', and set it's value to 'development'. Stop, de-register, and
then restart your application. Your application then should start in development mode,
which means autoreloading will work correctly.

Now, you can access your Redmine installation using the default username and password, admin/admin.
It may take a few seconds to load the front page the first time as the caches are populated.

Storing attachments on Amazon S3
--------------------------------

By default, Redmine will store uploaded files onto the filesystem alongside the code. For
many installations this works well; however, on Paasmaker, it will delete all the instance
files once it's done. This poses a problem for long term file storage with Redmine.

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
	  - name: postgres
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
should appear in the bucket automatically. Note that the upload will make Redmine
slower to upload files.

Check in your changes, and deploy as appropriate.

Updating Redmine
----------------

Around the beginning of 2013, Rails had a few security vulnerabilities,
and Redmine was sensitive to this because it's based on Rails.

To keep your Redmine installation secure, you should update your Redmine
installation. You can use this method to update to the latest version.

* Have an up to date checkout of your version of Redmine.
* Download the latest tar.gz release of Redmine. I fetched it from
  `the Redmine download page on RubyForge <http://rubyforge.org/frs/?group_id=1850>`_.
* Unpack it into a temporary directory. For example:

  .. code-block:: bash

  	$ tar -zxvf redmine-2.2.3.tar.gz
  	$ cp -Rv redmine-2.2.3/* /path/to/your/redmine/checkout

* Review the changes. In my example, I went to version 2.2.3. The only file
  that I had changed that was overridden was config/environment.rb, so I
  reverted that file, and then checked in all other changes.

  .. code-block:: bash

  	$ git status
  	$ git diff
  	$ git checkout config/environment.rb
  	$ git add .
  	$ git commit

* Make sure that you can still ``bundle install``. Quite likely you'll
  actually want to ``bundle update`` to fetch all the dependencies.

* Redeploy your version of Redmine using Paasmaker.

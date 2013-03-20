Ruby on Rails on Paasmaker
==========================

Paasmaker can easily support Ruby on Rails, and easily switch between ruby versions.
In fact, you can install as many versions of Ruby as you'd like and easily start
applications on any combination of these versions in one go.

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

Install Rails
-------------

At time of writing, we used Rails 3.2.13.

Install the Rails gem onto your machine, to give you the rails command line tool:

.. code-block:: bash

	$ gem install rails

Now make sure you're in the correct directory, and then use ``rails new`` to set up the
rails boilerplate. Then check in all the files as a pristine copy of Rails.

.. code-block:: bash

	$ cd paasmaker-rails-simple
	$ git init .
	$ rails new .
	$ git add .
	$ git commit

Now, we need to place in a manifest file, and adjust some configuration of rails. First start
by creating the ``manifest.yml`` file in the root, with these contents:

.. code-block:: yaml

	manifest:
	  format: 1

	application:
	  name: paasmaker-rails
	  prepare:
	    runtime:
	      plugin: paasmaker.runtime.ruby.rbenv
	      version: 1.9.3
	    commands:
	      - plugin: paasmaker.prepare.shell
	        parameters:
	          commands:
	            - bundle install

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
	            - bundle install
	            - rake db:migrate

	services:
	  - name: railsexample
	    plugin: paasmaker.service.mysql

We now need to configure rails to read in the configuration from Paasmaker. Also, include
gems to add support for MySQL and Postgres. Add the following gems to the ``Gemfile``:

.. code-block:: ruby

	gem "paasmaker-interface"
	gem "mysql2"
	gem "sqlite3"
	gem "pg"
	gem "thin"

	gem "activerecord-mysql-adapter"

And then update your local gems:

.. code-block:: bash

	$ bundle install

Now, you can edit ``config/environment.rb`` to make the following changes. The new block
is the one in the middle.

.. code-block:: ruby

	# In file config/environment.rb:

	# Load the rails application
	require File.expand_path('../application', __FILE__)

	# For Paasmaker, determine the rails environment.
	require 'paasmaker'
	interface = Paasmaker::Interface.new([])
	ENV['RAILS_ENV'] = interface.get_rails_env('production')

	# Store the interface into a global variable for later use.
	$PAASMAKER_INTERFACE = interface

	# Initialize the rails application
	PaasmakerRailsSimple::Application.initialize!

The next thing to do is to edit the configuration to insert the right values from the desired
service. Note that in the call to ``get_service()``, the name matches up with the service name
in the ``manifest.yml`` file. In ``config/database.yml``:

.. code-block:: yaml

	# SQLite version 3.x
	#   gem install sqlite3
	#
	#   Ensure the SQLite 3 gem is defined in your Gemfile
	#   gem 'sqlite3'

	<% interface = $PAASMAKER_INTERFACE %>
	<% database = interface.get_service('railsexample') %>

	production:
	  adapter: mysql2
	  database: "<%= database['database'] %>"
	  host: "<%= database['hostname'] %>"
	  username: "<%= database['username'] %>"
	  password: "<%= database['password'] %>"
	  port: <%= database['port'] %>
	  encoding: utf8

	development:
	  adapter: mysql2
	  database: "<%= database['database'] %>"
	  host: "<%= database['hostname'] %>"
	  username: "<%= database['username'] %>"
	  password: "<%= database['password'] %>"
	  port: <%= database['port'] %>
	  encoding: utf8

	# Warning: The database defined as "test" will be erased and
	# re-generated from your development database when you run "rake".
	# Do not set this db to the same as development or production.
	test:
	  adapter: sqlite3
	  database: db/test.sqlite3
	  pool: 5
	  timeout: 5000

Now, using the development mode plugin, create the application by supplying the directory
on your local machine. Paasmaker will allocate you a new database and set up your application.
Once it starts up correctly, you can view the front page, which will just be the default Rails
start page. In my example, the URL I got is `http://1.web.paasmaker-rails.test.local.paasmaker.net:42530/
<http://1.web.paasmaker-rails.test.local.paasmaker.net:42530/>`_.

.. NOTE::
	In development mode, the prepare and startup commands are not run. So you will need to
	make sure you've run ``bundle install`` before you try to start your applicaton. How
	to do database updates is described shortly.

Also, at the moment it will be running in ``production`` mode. This is not what you want for
development. To fix this, edit the workspace that you added the application to, and add
a key called ``RAILS_ENV``, and set it's value to ``development``. Stop, de-register, and
then restart your application. Your application then should start in development mode,
which means autoreloading will work. This makes it easier to develop as you don't have
to keep stopping and starting you application each time you make a change.

.. note::
	Just stopping your instance and starting it again is not enough. You must deregister
	it first, as Paasmaker only updates the instance metadata on instance registration.

Now that it's running, you will need to add ``paasmaker_web_env.sh`` to the .gitignore file.
You won't want to check in ``paasmaker_web_env.sh``, as it can't be shared between developers.
Also check in all the other changes up until this point, so you can see what was required to
get the application to this stage.

.. code-block:: bash

	$ echo "/paasmaker_env_web.sh" >> .gitignore
	$ git add .
	$ git commit

Developing with Rails
---------------------

As an example, we'll add a simple ActiveRecord ORM object, and work with it in the controller.
This is based on small sections of the `Rails getting started guide
<http://guides.rubyonrails.org/getting_started.html>`_, but covers how to integrate with Paasmaker.

Any commands that you run need to be done in the context of the Paasmaker instance. To do this,
the development mode writes out a shell script that sets up the correct environment. It's based
on your instance type name - so in our example, it's called ``paasmaker_env_web.sh``.

Generate an index controller, and an ORM object:

.. code-block:: bash

	$ ./paasmaker_env_web.sh rails generate controller home index
	$ rm public/index.html
	$ ./paasmaker_env_web.sh rails generate scaffold Post name:string title:string content:text
	$ ./paasmaker_env_web.sh rake db:migrate

Once you've done this, the Rails application will automatically reload. You can then see the index
page of your application by going to /home/index. Also, the scaffolding it has created can be used,
by visitng /posts.

If you want to use the rails console, just run it via the ``paasmaker_env_web.sh``, like so:

.. code-block:: bash

	$ ./paasmaker_env_web.sh rails console

Deploying to production with Rails
----------------------------------

The manifest file you checked in contains a section that is used to prepare the source code,
which just runs ``bundle install``. This sets up any gems on the server that's preparing the code.

The manifest file also has a section that runs commands prior to the startup. From the example,
you can see that it runs ``bundle install`` and then ``rake db:migrate``. This means when the new
version of your application starts, it will automatically migrate the database. You'll need to
keep this in mind when you go into production.

You can add more startup tasks if you need to, to dump out production assets to disk. Alternately,
you might be able to dump the production assets at prepare time, so this is only processed once,
as opposed to having to dump the assets for each startup.

By default, the Paasmaker interface will select production mode, so you can put any production
specific settings into that mode.
Service plugins
===============

Service plugins allow Paasmaker to supply service credentials to applications,
by creating or setting up the appropriate details. The strategy for doing so
depends highly on the service in question.

Service Strategies
------------------

The plugins that ship with Paasmaker use a few different strategies to supply
services to applications. They are designed to meet different needs and deployment
scenarios.

* External services. A service plugin can use an external service, create credentials
  on that service, and supply that to applications.

  For example, the default MySQL plugin, when asked to create a service, will
  contact an existing MySQL server, as given by the plugins configuration. Using
  the credentials provided, it will create a new user, with a password, and a blank
  database that can only be accessed by that new user. It will then pass these
  details back to the application for it to use.

* Managed services. To make development easier, some plugins are able to start their
  own instances of a service, and then grant access to those to applications.

  For example, the managed MySQL plugin will create a seperate MySQL instance just
  for itself, running on a different TCP port to any system installed MySQL. After that,
  the plugin works like the regular MySQL plugin; creating a user, password, and database
  per service, and supplying that to the application.

  Another example is the managed Redis plugin. Redis doesn't really have a concept of
  seperate databases for each applications - each instance is designed to be for a single
  application. To make it easier to use Redis, this plugin will start and manage a redis
  instance for applications, and supply each different application a seperate Redis instance
  so they won't interfere with each other.

  The advantage to having managed and non managed versions of the MySQL and Postgres services
  is that if they are configured with the same name - you can use it in development and
  move to production seamlessly later. It also means you are developing against the actual
  SQL database you're using in production, rather than an alternate like SQLite.

SERVICE_CREATE, SERVICE_DELETE, SERVICE_EXPORT
----------------------------------------------

SERVICE_CREATE, SERVICE_DELETE, and SERVICE_EXPORT are handled by a single base class,
``BaseService``. Your implementation should implement both SERVICE_CREATE and SERVICE_DELETE,
and implement SERVICE_EXPORT if it makes sense for your service.

.. autoclass:: paasmaker.pacemaker.service.base.BaseService
    :members:
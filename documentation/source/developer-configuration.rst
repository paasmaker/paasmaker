
Configuration
=================

Inside the system, a single ``Configuration`` object handles capturing all the context
that is the configuration of the system, and also allowing access to database, Redis,
and other connections required for operation.

By having a central object to handle this that gets passed around, in tests it can
be replaced with a stub object that does a few different things.

Classes
-------

.. autoclass:: paasmaker.common.configuration.Configuration
    :members:

.. autoclass:: paasmaker.common.configuration.ConfigurationStub
    :members:
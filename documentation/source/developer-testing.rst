
Testing
=================

To make it easier to develop and test Paasmaker, some additional code
was developed. The primary one to note is the ConfigurationStub, which
is used in unit tests instead of a Configuration object.

As much of Paasmaker as possible is unit tested. Some things are quite
difficult to unit test, and at that juncture the integration tests
take over.

Unit Testing
------------

TODO: Document the configuration stub here.
TODO: Document the BaseControllerTest here.

Each file, where possible, should contain it's own unit tests to
match the class. Depending on what your unit test needs, you can
decend from the following base classes:

* **unittest.TestCase**: Where you have pure python code that does
    not do any networking or asyncrhonous calls.
* **tornado.testing.AsyncTestCase**: Where you require a Tornado
    IOLoop, but nothing of Paasmaker.
* **BaseControllerTest**: Where you require some components of
    Paasmaker, or web controllers. The BaseControllerTest handles
    creating a suitable ConfigurationStub, starting and stopping
    relevant Redis daemons on demand, and setting up any controllers
    required by your unit test. You can control what components of
    Paasmaker are set up as well by adjusting a class variable.

Integration Testing
-------------------

.. autoclass:: paasmaker.util.multipaas.MultiPaas
    :members:

.. autoclass:: paasmaker.util.multipaas.Executor
    :members:

.. autoclass:: paasmaker.util.multipaas.Paasmaker
    :members:
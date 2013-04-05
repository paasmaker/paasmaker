Tornado-Redis
=============

Asynchronous [Redis](http://redis.io/) client for the [Tornado Web Server](http://tornadoweb.org/).

This is a fork of [brükva](https://github.com/evilkost/brukva) redis client
modified to be used via Tornado's native 'tornado.gen' interface instead
of 'adisp' call dispatcher.

Tornado-Redis is licensed under the Apache Licence, Version 2.0
(http://www.apache.org/licenses/LICENSE-2.0.html).

Installation
------------

You may install the tornado-redis client library using [pip](http://pypi.python.org/pypi/pip) or
[easy_install](http://peak.telecommunity.com/DevCenter/EasyInstall) tools:

    pip install tornado-redis

or

    easy_install install tornado-redis

To build and install the tornado-redis client library from source, clone the
git://github.com/leporo/tornado-redis.git repository or download the archive
from the [download page](https://github.com/leporo/tornado-redis/downloads)
and extract it into the separate directory.
Then execute the following commands in the source directory:

    python setup.py build
    python setup.py install


Usage
-----

	import tornadoredis
	import tornado.web
	import tornado.gen

	...

	c = tornadoredis.Client()
	c.connect()

	...

	class MainHandler(tornado.web.RequestHandler):
	    @tornado.web.asynchronous
	    @tornado.gen.engine
	    def get(self):
	        foo = yield tornado.gen.Task(c.get, 'foo')
	        bar = yield tornado.gen.Task(c.get, 'bar')
	        zar = yield tornado.gen.Task(c.get, 'zar')
	        self.set_header('Content-Type', 'text/html')
	        self.render("template.html", title="Simple demo", foo=foo, bar=bar, zar=zar)

Using Pipelines
---------------

Pipelines correspond to the [Redis transaction feature](http://redis.io/topics/transactions).

Here is a simple example of pipeline feature usage:

    client = Client()
    # Create a 'Pipeline' to pack a bunldle of Redis commands
    # and send them to a Redis server in a single request
    pipe = client.pipeline()
    # Add commands to a bundle
    pipe.hset('foo', 'bar', 1)
    pipe.expire('foo', 60)
    # Send them to the Redis server and retrieve execution results
    res_hset, res_expire = yield gen.Task(pipe.execute)

Note that nothing is being sent to the Redis server until the `pipe.execute`
method call so there is no need to wrap a `pipe.hset` and `pipe.expire`
calls with the `yield gen.Task(...)` statement.

Connection Pool Support
-----------------------

To limit a number of redis server connections opened by an application
and reuse them the tornado-redis library has the connection pooling support.
To activate it, create the ConnectionPool object instance and pass it
as connection_pool argument to the Client object:


    CONNECTION_POOL = tornadoredis.ConnectionPool(max_connections=500,
                                                  wait_for_available=True)
    ...
	class MainHandler(tornado.web.RequestHandler):
	    @tornado.web.asynchronous
	    @tornado.gen.engine
	    def get(self):
            c = tornadoredis.Client(connection_pool=CONNECTION_POOL)
            info = yield tornado.gen.Task(c.info)
            ....
            # Release the connection to be reused by connection pool.
            yield tornado.gen.Task(c.disconnect)
            self.render(....)


Note that you have to add a `disconnect` method call
at the end of the code block using the Client instance to release the
pooled connection (it's to be fixed it future library releases).

See the [connection pool demo](https://github.com/leporo/tornado-redis/tree/master/demos/connection_pool)
for an example of the 'connection pool' feature usage.

Demos
-----

Check the [Demos folder](https://github.com/leporo/tornado-redis/tree/master/demos)
for tornado-redis usage examples.

Here is the list of demo applications available from this repository:

simple - a very basic example of tornado-redis client usage

connection_pool - a 'connection pool' feature demo

websockets - a demo web chat application using WebSockets
 and Redis' [PubSub feature](http://redis.io/topics/pubsub).


Running Tests
-------------

The redis server must be started on the default (:6379) port.

Use the following command to run the test suite:

	python -m tornado.testing tornadoredis.tests


Credits and Contributors
------------------------

The [brükva](https://github.com/evilkost/brukva) project has been started
by [Konstantin Merenkov](https://github.com/kmerenkov)
but seem to be not maintained any more.

[evilkost](https://github.com/evilkost)

[Matt Dawson](https://github.com/mattd)

[maeldur](https://github.com/maeldur)

[Olivier Yiptong](https://https://github.com/oyiptong)

[Juarez Bochi](https://github.com/jbochi)

[Jakub Roztocil](https://github.com/jkbr)

[nizox](https://github.com/nizox)

[Lessandro Mariano](https://github.com/lessandro)

The Tornado-Redis project's source code and 'tornado-redis' PyPI package
are maintained by [Vlad Glushchuk](https://github.com/leporo).

Tornado is an open source version of the scalable, non-blocking web server
and tools that power FriendFeed. Documentation and downloads are
available at http://www.tornadoweb.org/
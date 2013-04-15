The Tornado Web framework
=========================

Paasmaker relies heavily on the `Tornado web framework <http://www.tornadoweb.org/>`_.
Tornado is more than a web framework though; it's a complete asynchronous IO system
similiar to `Twisted <http://twistedmatrix.com/trac/>`_ or `gevent <http://www.gevent.org/>`_.

Tornado was chosen because a lot of tasks that Paasmaker performs are IO bound,
which is well suited to this framework, and also removed the need to consider
locks between threads (irrespective of the Python `GIL <http://wiki.python.org/moin/GlobalInterpreterLock>`_).

Asynchronous code and callbacks
-------------------------------

If you're not familiar with asynchronous code in general, it can be confusing to
start off with. There are plenty of documents on the internet that can give it
a much better treatment than this document can, but basically, instead of code
flowing from top to bottom, you make a request, and supply a function that is
called when that request is complete. Here is a simple example of Tornado's async
HTTP library::

	def handle_request(response):
	    if response.error:
	        print "Error:", response.error
	    else:
	        print response.body
	    ioloop.IOLoop.instance().stop()

	http_client = httpclient.AsyncHTTPClient()
	http_client.fetch("http://www.google.com/", handle_request)

You will note that this code looks a little backwards: what happens after
the response is fetched appears in the code first, and then the request
appears afterwards. In this one, I've added numbers to show the order
of execution::

	def handle_request(response):
	    # 3
	    if response.error:
	        print "Error:", response.error
	    else:
	        print response.body

	# 1
	http_client = httpclient.AsyncHTTPClient()
	# 2
	http_client.fetch("http://www.google.com/", handle_request)

Paasmaker uses a mix of anonymous functions or class functions as callbacks,
so check the code carefully.

Asynchronous Python basic HOWTO
-------------------------------

Most plugins are asynchronous. You should wherever possible make your code
asynchronous, as otherwise it will block other parts of the system as it's running.

There are a few common tasks for which asynchronous examples are provided below.

Running an external process. The built in ``subprocess`` module is blocking, and running
a process via this would block. You could background the process, but then it would
be hard to figure out when it has exited, and also to grab it's output.

Github user bergundy wrote a `popen Tornado gist <https://gist.github.com/bergundy/3492507>`_.
It's been submitted for inclusion in Tornado, but has not yet been accepted, so Paasmaker
distributes it's own version in ``paasmaker.util.popen.Popen``.

.. code-block:: python

	def on_exit(rc):
	    # rc is the exit code.
	    pass
	def on_stdout(chunk):
	    # chunk is a string, part of the stdout output
	    # (won't be line aligned)
	    pass
	def on_stderr(chunk):
	    # same as on_stdout().
	    pass

	process = Popen(
	    ['command'],
	    io_loop=io_loop,
	    close_fds=True,
	    on_exit=on_exit,
	    on_stdout=on_stdout,
	    on_stderr=on_stderr
	)

Sleeping. The built in ``time.sleep()`` will block the whole process. Tornado provides
a helpful `add_timeout() <http://www.tornadoweb.org/en/branch2.4/ioloop.html#tornado.ioloop.IOLoop.add_timeout>`_
function that can be used to accomplish the same thing:

.. code-block:: python

	def time_expired():
	    pass

	# Wait 5 seconds.
	self.configuration.io_loop.add_timeout(time.time() + 5, time_expired)

Short synchronous work that can't easily be made asynchronous. Paasmaer provides
a :class:`~paasmaker.util.threadcallback.ThreadCallback` class, that can be used to
push some work onto a thread and call us back (on the main thread) once done.
The documentation for that class has a simple example on how to use it.
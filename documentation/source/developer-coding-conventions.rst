Coding Conventions
==================

Paasmaker does not currently have a strict set of coding conventions
that it adheres to. But most of the current code was written with
a series of conventions in mind, which are documented here, as that
may assist in reading the code.

Python
------

Python code loosely follows `PEP-8 <http://www.python.org/dev/peps/pep-0008/>`_,
and is geared towards being readable. This is tricky with asynchronous code though.

There are a few major differences from PEP-8:

* Tabs are used for indentation instead of spaces. This is an arbitrary choice
  made by the original developer.
* The maximum line length is unlimited, although it should be kept short where
  possible. To assist in this, long function calls tend to be broken out as
  in this example::

  	function_call(
  		parameter1,
  		parameter2,
  		keywordargument=value
  	)


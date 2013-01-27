
import logging
import threading
import socket
import sys

import tornado.testing

class ThreadCallback(threading.Thread):
	def __init__(self, io_loop, callback, error_callback, **kwargs):
		"""
		A helper class to spawn a new thread, do some blocking work in that,
		and then asychronously call the supplied callback once done.

		This class is meant to be subclassed to perform the specific work that
		you need to do. It's designed to be a way to use external syncrhonous
		libraries to do a little bit of work, rather than having to rewrite them
		or find a synchronous version of those libraries.

		CAUTION: error_callback MUST have the signature (message, exception)
		as the exception handling here won't print errors if this is not the
		case.
		"""
		super(ThreadCallback, self).__init__(**kwargs)
		self.io_loop = io_loop
		self._user_callback = tornado.stack_context.wrap(callback)
		self._user_error_callback = tornado.stack_context.wrap(error_callback)
		self._exception = None
		self._user_callback_args = []
		self._user_callback_kwargs = {}
		self.input_args = []
		self.input_kwargs = {}

	def run(self):
		try:
			self._work(*self.input_args, **self.input_kwargs)
		except Exception, ex:
			# Catch ALL the exceptions.
			self._exception = ex

		# Add a callback to handle the result.
		# This transfers control back to the main IO loop.
		self.io_loop.add_callback(self._do_result_callback)

	def _work(self, *args, **kwargs):
		"""
		Override this in your subclass to actually perform your work.

		If you fail, throw an exception, and that will be passed back to
		the error_callback.

		If you finish, set self.callback_args to a list of arguments
		to call the callback function with. You can also set self.callback_kwargs
		as well.

		You should adjust the signature of this function to be any
		named or keyword arguments that make sense for your work.
		"""
		pass

	def work(self, *args, **kwargs):
		"""
		Kick off this worker process. The supplied arguments
		are given to the ``_work()`` function.
		"""
		self.input_args = args
		self.input_kwargs = kwargs

		self.start()

	def _callback(self, *args, **kwargs):
		"""
		Call the callback with all the arguments supplied. Your subclass
		should call this when it's done.
		"""
		self._user_callback_args = args
		self._user_callback_kwargs = kwargs


	def _do_result_callback(self):
		if self._exception:
			self._user_error_callback(str(self._exception), exception=self._exception)
		else:
			self._user_callback(*self._user_callback_args, **self._user_callback_kwargs)

class ThreadCallbackSuccess(ThreadCallback):

	def _work(self, input_one):
		self._callback('bar')

class ThreadCallbackException(ThreadCallback):

	def _work(self, input_two):
		raise Exception("Nope.")

class ThreadCallbackTest(tornado.testing.AsyncTestCase):
	def _error(self, message, exception=None):
		self.stop(exception)

	def test_simple(self):
		# Normal execution.
		lookup = ThreadCallbackSuccess(self.io_loop, self.stop, self._error)
		lookup.work('test')

		result = self.wait()
		self.assertEquals(result, "bar", "Unexpected result.")

		# Missing arguments to the work function.
		lookup = ThreadCallbackSuccess(self.io_loop, self.stop, self._error)
		lookup.work()

		result = self.wait()
		self.assertTrue(isinstance(result, Exception), "Result was not an exception.")

		# And something that throws an exception.
		lookup = ThreadCallbackException(self.io_loop, self.stop, self._error)
		lookup.work("argument")

		result = self.wait()
		self.assertTrue(isinstance(result, Exception), "Result was not an exception.")
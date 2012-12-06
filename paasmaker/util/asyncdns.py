
import logging
import threading
import socket
import sys

import tornado.testing

class AsyncDNS(threading.Thread):
	def __init__(self, io_loop, query, callback, error_callback, mode='auto', **kwargs):
		"""
		A class to spawn a new thread to do a DNS lookup, to prevent blocking
		the IO loop. The mode switches between doing IPv4 and IPv6 lookups - by
		default it will choose based on the system, which would choose correctly
		for external services. However, this probably won't exhibit the correct
		result for applications, because they might need to be specifically asked
		to listen on IPv6.

		CAUTION: error_callback MUST have the signature (message, exception)
		as the exception handling here won't print errors if this is not the
		case.
		"""
		super(AsyncDNS, self).__init__(**kwargs)
		self.io_loop = io_loop
		self.query = query
		self.callback = tornado.stack_context.wrap(callback)
		self.error_callback = tornado.stack_context.wrap(error_callback)
		self.result = None
		self.exception = None
		self.mode = mode

	def run(self):
		try:
			family = 0
			if self.mode == 'ipv4':
				family = socket.AF_INET
			if self.mode == 'ipv6':
				family = socket.AF_INET6

			initial_result = socket.getaddrinfo(self.query, None, family)

			# Assume that the first one passed back is the preferred one.
			if len(initial_result) > 0:
				self.result = initial_result[0][4][0]
			else:
				# Nothing returned. Probably the DNS server returned no
				# records at all...
				self.result = None

		except Exception, ex:
			self.exception = ex
		self.io_loop.add_callback(self._do_result_callback)

	def _do_result_callback(self):
		if self.exception:
			self.error_callback(str(self.exception), exception=self.exception)
		else:
			self.callback(self.result)

class AsyncDNSTest(tornado.testing.AsyncTestCase):
	def _error(self, message, exception):
		self.stop(exception)

	def test_simple(self):
		lookup = AsyncDNS(self.io_loop, 'local.paasmaker.net', self.stop, self.stop)
		lookup.start()

		result = self.wait()

		# Should have return IPv6 loopback... TODO: This may not be true.
		self.assertEquals(result, "::1", "Unexpected lookup.")

		# Try again, this time force IPv4.
		lookup = AsyncDNS(self.io_loop, 'local.paasmaker.net', self.stop, self.stop, mode='ipv4')
		lookup.start()

		result = self.wait()
		self.assertEquals(result, "127.0.1.1", "Unexpected lookup.")

		# Check localhost.
		lookup = AsyncDNS(self.io_loop, 'localhost', self.stop, self.stop)
		lookup.start()

		result = self.wait()
		self.assertEquals(result, "::1", "Unexpected lookup.")

	def test_failed(self):
		lookup = AsyncDNS(self.io_loop, 'noexist.paasmaker.net', self.stop, self._error)
		lookup.start()

		result = self.wait()
		self.assertEquals(type(result), socket.gaierror, "Wrong exception returned.")

	def test_nxdomain(self):
		lookup = AsyncDNS(self.io_loop, 'ohsurelythisdoesntpossiblyexist.com', self.stop, self._error)
		lookup.start()

		result = self.wait()
		self.assertEquals(type(result), socket.gaierror, "Wrong exception returned.")
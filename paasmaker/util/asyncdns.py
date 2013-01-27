
import logging
import socket
import sys

from threadcallback import ThreadCallback

import tornado.testing

class AsyncDNS(ThreadCallback):
	"""
	Look up DNS asynchronously. This uses a thread to do the lookup,
	and calls the callback once complete.

	CAUTION: error_callback MUST have the signature (message, exception)
	as the exception handling here won't print errors if this is not the
	case.
	"""
	def lookup(self, query, mode='auto'):
		"""
		Lookup the given DNS query.

		:arg str query: The hostname to query.
		:arg str mode: The mode for the lookup. 'auto' will choose
			IPv6 or IPv4 depending on the machine. 'ipv4' or 'ipv6'
			will force one of those two results.
		"""
		self.work(query, mode=mode)

	def _work(self, query, mode='auto'):
		family = 0
		if mode == 'ipv4':
			family = socket.AF_INET
		if mode == 'ipv6':
			family = socket.AF_INET6

		initial_result = socket.getaddrinfo(query, None, family)

		# Assume that the first one passed back is the preferred one.
		if len(initial_result) > 0:
			self.callback_args = [initial_result[0][4][0]]
		else:
			# Nothing returned. Probably the DNS server returned no
			# records at all...
			self.callback_args = [None]

class AsyncDNSTest(tornado.testing.AsyncTestCase):
	def _error(self, message, exception=None):
		self.stop(exception)

	def test_simple(self):
		lookup = AsyncDNS(self.io_loop, self.stop, self._error)
		lookup.lookup('local.paasmaker.net')

		result = self.wait()

		# Should have returned a loopback address.
		self.assertIn(result, ["::1", "127.0.1.1"], "Unexpected lookup.")

		# Try again, this time force IPv4.
		lookup = AsyncDNS(self.io_loop, self.stop, self._error)
		lookup.lookup('local.paasmaker.net', mode='ipv4')

		result = self.wait()
		self.assertEquals(result, "127.0.1.1", "Unexpected lookup.")

		# Check localhost.
		lookup = AsyncDNS(self.io_loop, self.stop, self._error)
		lookup.lookup('localhost')

		result = self.wait()
		self.assertIn(result, ["::1", "127.0.1.1"], "Unexpected lookup.")

	def test_failed(self):
		lookup = AsyncDNS(self.io_loop, self.stop, self._error)
		lookup.lookup('noexist.paasmaker.net')

		result = self.wait()
		self.assertEquals(type(result), socket.gaierror, "Wrong exception returned.")

	def test_nxdomain(self):
		lookup = AsyncDNS(self.io_loop, self.stop, self._error)
		lookup.lookup('ohsurelythisdoesntpossiblyexist.com')

		result = self.wait()
		self.assertEquals(type(result), socket.gaierror, "Wrong exception returned.")
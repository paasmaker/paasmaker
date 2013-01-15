
import subprocess
import unittest
import platform
import time
import logging
import re

import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NoFreePortException(Exception):
	"""
	Exception for when no free port could be found in the range
	requested.
	"""
	pass

class FreePortFinder(object):
	"""
	A class to locate free TCP ports on the system, and confirm
	that they're not in use. On Linux, uses a call to the external
	program ``netstat`` to perform its actions.
	"""

	def __init__(self):
		"""
		Create an instance of the free port finder. Some state
		is retained between calls to ``free_in_range()`` to make
		it faster and to allow it to make better choices.
		"""
		self.last_allocated = None
		self.preallocated = set()
		# looking for port numbers: search for hex, wildcard (* or ::),
		# or IPv6 square bracket characters, followed by colon or dot
		# (BSD / OS X netstat output), followed by some digits
		self.netstat_wrangler = re.compile('[0-9a-f\*\:\]][\.\:](\d+)(?:\s|\Z)')

	def add_allocated_port(self, port):
		"""
		Add a pre-allocated port. This is used to avoid using
		certain ports because they've already been assigned.

		:arg int port: Port to mark as allocated.
		"""
		if isinstance(port, list):
			self.preallocated.update(port)
		else:
			self.preallocated.add(port)

	def remove_allocated_port(self, port):
		"""
		Remove a pre-allocated port. This is used to allow
		the port to be chosen again when the system knows
		it can be used again.

		:arg int port: The port to remove.
		"""
		if port in self.preallocated:
			self.preallocated.remove(port)

	def free_in_range(self, lower, upper, complete_scan=False):
		"""
		Find a free port in the given range, inclusively.

		This attempts to use ``netstat`` as few times as possible.

		:arg int lower: The lower bound of ports to search through.
		:arg int upper: The upper bound of ports to search through.
		:arg bool complete_scan: Scan the entire range regardless of
			the previous upper and lower bounds. This is intended to be
			used internally by the function to scan the part of the range
			that it may have missed due to previous port requests.
		"""
		start = lower
		using_last_allocated = False
		if self.last_allocated and not complete_scan:
			using_last_allocated = True
			if self.last_allocated < lower or self.last_allocated > upper:
				# Range has changed!
				start = lower
			else:
				start = self.last_allocated + 1
		# Fetch the current list of ports.
		ports_in_use = self._fetch_netstat()
		# Now begin the search.
		port = start
		free = (port not in ports_in_use) and (port not in self.preallocated)
		while not free and port < upper:
			port += 1
			free = (port not in ports_in_use) and (port not in self.preallocated)
		if not free:
			# If we were using the last allocated port,
			# we might not have scanned the bottom of the range.
			if using_last_allocated:
				# Scan again from the bottom.
				self.free_in_range(lower, upper, complete_scan=True)
			else:
				raise NoFreePortException("Can't find a free port between %d and %d." % (lower, upper))
		# Return the port.
		self.last_allocated = port
		return port

	def in_use(self, port):
		"""
		Quickly check if a port is in use.

		This is not intended to be used to allocate ports.

		:arg int port: The port to test.
		"""
		ports_in_use = self._fetch_netstat()
		return (port in ports_in_use)

	def _fetch_netstat(self):
		# TODO: This is HIGHLY platform specific, but it's fast.
		# TODO: This will block the whole process... but only for ~20ms.
		# NOTE: The docs say not to use subprocess.PIPE with the command
		# below because it can cause the call to block if that pipe
		# fills up. However, I'm using this to prevent the stderr from
		# being printed out - and relying on the fact that it won't
		# print very much output to stderr.
		# On Linux, -lt shows listening TCP ports
		# On Mac OS X, -aL shows all open ports with a listening queue
		# (in both cases -n shows numeric ports)
		if platform.system() == 'Linux':
			command = ['netstat', '-ltn']
		if platform.system() == 'Darwin':
			command = ['netstat', '-aLn']
		if platform.system() == 'Windows':	# abandon all hope, ye who enter here
			command = ['netstat', '-na', '-p', 'tcp']
		output = subprocess.check_output(command, stderr=subprocess.PIPE)

		# Run a regexp match to find open ports in the netstat output,
		# then return the results as a dict of integers for quick lookups
		mapped_ports = {}
		ports = self.netstat_wrangler.findall(output)
		for port in ports:
			mapped_ports[int(port)] = True
		return mapped_ports

	def wait_until_port_used(self, io_loop, port, timeout, callback, timeout_callback):
		"""
		Wait until the given port is in use. Waits up to the supplied timeout,
		calling the callback when it succeeds, or the timeout_callback if
		it doesn't reach that state in the given timeout. Requires a tornado
		IO loop to schedule callbacks to continue checking.

		:arg IOloop io_loop: The Tornado IO loop to use.
		:arg int port: The port to wait for.
		:arg int timeout: The number of seconds to wait for before
			calling the timeout_callback.
		:arg callable callback: The callback function when it's in the appropriate
			state. It is supplied a single string argument that is a message.
		:arg callback timeout_callback: The callback function for when the timeout
			has expired. It is supplied a single string argument that is a message.
		"""
		self._wait_until_port_state(io_loop, port, True, timeout, callback, timeout_callback)

	def wait_until_port_free(self, io_loop, port, timeout, callback, timeout_callback):
		"""
		This is the inverse of ``wait_until_port_used()``.
		"""
		self._wait_until_port_state(io_loop, port, False, timeout, callback, timeout_callback)

	def _wait_until_port_state(self, io_loop, port, state, timeout, callback, timeout_callback):
		# Wait until the port is in a different state.
		end_timeout = time.time() + timeout

		def wait_for_state():
			if self.in_use(port) == state:
				# And say that we're done.
				logger.debug("Port %d is now in state %s.", port, str(state))
				callback("In appropriate state.")
			else:
				logger.debug("Port %d not yet in state %s, waiting longer.", port, str(state))
				if time.time() > end_timeout:
					timeout_callback("Failed to end up in appropriate state in time.")
				else:
					# Wait a little bit longer.
					io_loop.add_timeout(time.time() + 0.1, wait_for_state)

		logger.debug("Adding timeout waiting for port %d to be %s.", port, str(state))
		io_loop.add_timeout(time.time() + 0.1, wait_for_state)

class FreePortFinderTest(tornado.testing.AsyncTestCase):
	def test_free(self):
		finder = FreePortFinder()

		port = finder.free_in_range(10000, 10100)
		self.assertTrue(port >= 10000 and port <= 10100)

		# Change the range, and try again.
		port = finder.free_in_range(10050, 10100)
		self.assertTrue(port >= 10000 and port <= 10100)

	def test_allocated(self):
		finder = FreePortFinder()

		port = finder.free_in_range(10000, 10100)
		self.assertEquals(port, 10000)

		# Mask out the following ports.
		finder.add_allocated_port(10000)
		finder.add_allocated_port(10002)

		# And now we should be returned ports around that.
		port = finder.free_in_range(10000, 10100)
		self.assertNotIn(port, [10000, 10002])
		port = finder.free_in_range(10000, 10100)
		self.assertNotIn(port, [10000, 10002])

		# Add a few more, via a list.
		finder.add_allocated_port([10004, 10006])

		port = finder.free_in_range(10000, 10100)
		self.assertNotIn(port, [10004, 10006])
		port = finder.free_in_range(10000, 10100)
		self.assertNotIn(port, [10004, 10006])

		finder = FreePortFinder()
		finder.add_allocated_port(10000)

		# Remove some allocated ports, and then see if we get it.
		finder.remove_allocated_port(10000)

		port = finder.free_in_range(10000, 10100)
		self.assertEquals(port, 10000)

	def test_finder_in_use(self):
		finder = FreePortFinder()

		try:
			port = finder.free_in_range(22, 22)
			self.assertTrue(False, "Found port 22 was free.")
		except NoFreePortException, ex:
			self.assertTrue("Didn't find port 22 as free.")

		# Try again, but go 22->24. One of those should be free.
		port = finder.free_in_range(22, 24)
		self.assertTrue(port == 23 or port == 24)

	def test_in_use(self):
		finder = FreePortFinder()

		self.assertTrue(finder.in_use(22), "Found port 22 was free.")
		self.assertFalse(finder.in_use(1), "Didn't find port 1 as free.")

	def test_wait_for_in_use(self):
		finder = FreePortFinder()

		def success(message):
			self.stop(True)

		def failed(message):
			self.stop(False)

		# Test with a port that is already in use.
		finder.wait_until_port_used(self.io_loop, 22, 0.2, success, failed)
		result = self.wait()

		self.assertTrue(result, "Port was not in use.")

		# Test with a port that is not in use - should call the failed callback.
		finder.wait_until_port_used(self.io_loop, 23, 0.2, success, failed)
		result = self.wait()

		self.assertFalse(result, "Port was in use.")

		# Try the reverse.
		finder.wait_until_port_free(self.io_loop, 22, 0.2, success, failed)
		result = self.wait()

		self.assertFalse(result, "Port was free.")

		finder.wait_until_port_free(self.io_loop, 23, 0.2, success, failed)
		result = self.wait()

		self.assertTrue(result, "Port was not free.")

if __name__ == '__main__':
	unittest.main()

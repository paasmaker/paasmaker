import subprocess
import unittest
import platform
import time
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NoFreePortException(Exception):
	pass

class FreePortFinder(object):
	"""
	A class to locate free TCP ports on the system, and confirm
	that they're not in use.
	"""

	def __init__(self):
		self.last_allocated = None
		self.preallocated = set()

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
		if port in self.preallocated:
			self.preallocated.remove(port)

	def free_in_range(self, lower, upper, complete_scan=False):
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
		output = self.fetch_netstat()
		# Now begin the search.
		port = start
		free = (output.find(":%d " % port) == -1) and (port not in self.preallocated)
		while not free and port < upper:
			port += 1
			free = (output.find(":%d " % port) == -1) and (port not in self.preallocated)
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
		output = self.fetch_netstat()
		return (output.find(":%d " % port) != -1)

	def fetch_netstat(self):
		# TODO: This is HIGHLY platform specific, but it's fast.
		# TODO: This will block the whole process... but only for ~20ms.
		# NOTE: The docs say not to use subprocess.PIPE with the command
		# below because it can cause the call to block if that pipe
		# fills up. However, I'm using this to prevent the stderr from
		# being printed out - and relying on the fact that it won't
		# print very much output to stderr.
		if platform.system() == 'Linux':
			command = ['netstat', '-ltnp']
		if platform.system() == 'Windows':
			command = ['netstat', '-na', '-p', 'tcp']
		output = subprocess.check_output(command, stderr=subprocess.PIPE)
		# Post process the output a little bit.
		raw_lines = output.split("\n")
		lines = []
		for line in raw_lines:
			if line.find("LISTEN") != -1:
				lines.append(line)
		output = "\n".join(lines)
		return output

	def wait_until_port_used(self, io_loop, port, timeout, callback, timeout_callback):
		self.wait_until_port_state(io_loop, port, True, timeout, callback, timeout_callback)
	def wait_until_port_free(self, io_loop, port, timeout, callback, timeout_callback):
		self.wait_until_port_state(io_loop, port, False, timeout, callback, timeout_callback)

	def wait_until_port_state(self, io_loop, port, state, timeout, callback, timeout_callback):
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

class FreePortFinderTest(unittest.TestCase):
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

if __name__ == '__main__':
	unittest.main()

import subprocess
import unittest

class NoFreePortException(Exception):
	pass

class FreePortFinder:
	def __init__(self):
		self.last_allocated = None
		self.preallocated = set()

	def add_allocated_port(self, port):
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
		# TODO: This is HIGHLY platform specific, but it's fast.
		# TODO: This will block the whole process... but only for ~20ms.
		# NOTE: The docs say not to use subprocess.PIPE with the command
		# below because it can cause the call to block if that pipe
		# fills up. However, I'm using this to prevent the stderr from
		# being printed out - and relying on the fact that it won't
		# print very much output to stderr.
		output = subprocess.check_output(['netstat', '-ltnp'], stderr=subprocess.PIPE)
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

class FreePortFinderTest(unittest.TestCase):
	def test_free(self):
		finder = FreePortFinder()

		port = finder.free_in_range(10000, 10100)
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

	def test_in_use(self):
		finder = FreePortFinder()

		try:
			port = finder.free_in_range(22, 22)
			self.assertTrue(False, "Found port 22 was free.")
		except NoFreePortException, ex:
			self.assertTrue("Didn't find port 22 as free.")

		# Try again, but go 22->24. One of those should be free.
		port = finder.free_in_range(22, 24)
		self.assertTrue(port == 23 or port == 24)

if __name__ == '__main__':
	unittest.main()

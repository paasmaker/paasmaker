
import hashlib
import os
import tempfile
import logging

import tornado.testing

class StreamingChecksum(object):
	"""
	Helper class to calculate the MD5 checksum of a file, but cooperate with
	the IO loop so as not to grind the whole process to a halt. Also logs it's
	progress to the supplied logger, to provide feedback for users as to what
	it's up to.
	"""
	def __init__(self, target, io_loop, logger, chunk_size=204800):
		"""
		Set up a new checksummer.
		target: the target file (must exist)
		io_loop: the IO loop to schedule on.
		logger: the logger to log progress to.
		chunk_size: how much to read from the file each time.
		"""
		self.target = target
		self.io_loop = io_loop
		self.logger = logger
		self.chunk_size = chunk_size

		self.total_size = os.path.getsize(target)
		self.current_size = 0

	def start(self, callback):
		"""
		Kick off the checksumming process, and call back
		the supplied callback once done.
		"""
		self.callback = callback
		self.fp = open(self.target, 'rb')
		self.md5 = hashlib.md5()
		self.io_loop.add_callback(self.loop)

	def loop(self):
		"""
		Read the next section of file, updating the checksum
		or returning the result as appropriate.
		"""
		section = self.fp.read(self.chunk_size)
		if section == '':
			# End of file.
			self.fp.close()
			checksum = self.md5.hexdigest()
			self.logger.info("Checksum complete. Value %s", checksum)
			self.callback(checksum)
		else:
			# Update it, and keep going.
			self.md5.update(section)
			self.current_size += len(section)
			percent = 1.0
			if self.total_size > 0:
				percent = (float(self.current_size) / float(self.total_size)) * 100
			self.logger.info("Read %d/%d bytes (%0.1f%%)", self.current_size, self.total_size, percent)
			self.io_loop.add_callback(self.loop)

class StreamingChecksumTest(tornado.testing.AsyncTestCase):
	def test_simple(self):
		test_file = tempfile.mkstemp()[1]

		# Put some data into that test file.
		fp = open(test_file, 'w')
		for i in range(500):
			fp.write("test" * 1024)
		fp.close()

		calc = StreamingChecksum(test_file, self.io_loop, logging)
		calc.start(self.stop)

		checksum = self.wait()

		self.assertEquals(checksum, '164d0dff959eeb51532cd9c7f56ed9d7', "Checksum wasn't as expected.")

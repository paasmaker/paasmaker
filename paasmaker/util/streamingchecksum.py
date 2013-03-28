#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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

	:arg str target: The target file to calculate the checksum of.
	:arg IOLoop io_loop: The IO loop to operate on.
	:arg LoggerAdapter logger: The logger to log progress to (logs to
		the INFO level).
	:arg int chunk_size: How much of the file to read on each iteration.
	"""
	def __init__(self, target, io_loop, logger, chunk_size=204800):
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

		:arg callable callback: The callback to call when completed.
			The callback is called with a single string argument,
			which is the checksum.
		"""
		self.callback = callback
		self.fp = open(self.target, 'rb')
		self.md5 = hashlib.md5()
		self.io_loop.add_callback(self._loop)

	def _loop(self):
		# Read the next section of the file.
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
			self.io_loop.add_callback(self._loop)

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
